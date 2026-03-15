from typing import List, Tuple, Dict, Optional
import structlog
from rapidfuzz import process, fuzz # Using rapidfuzz instead of fuzzywuzzy

from apps.api.agents.competitor_mapper.models import (
    ResponseRow,
    CompetitorMention,
    BrandMentionExtraction,
    LLMExtractionResult,
    SingleCompetitorExtraction,
    BrandCompetitiveStats,
)
from apps.api.agents.competitor_mapper.llm_caller import extract_competitor_data_with_llm
from apps.api.agents.competitor_mapper.prompts import build_extraction_prompt

log = structlog.get_logger(__name__)

async def extract_mentions_for_response(
    response_row: ResponseRow,
    brand_name: str,
    competitor_names: List[str],
    log_ctx: structlog.BoundLogger,
) -> Tuple[List[CompetitorMention], Optional[BrandMentionExtraction]]:
    """
    Extracts competitor and brand mentions for a single audit response using LLM.
    """
    local_log_ctx = log_ctx.bind(response_id=response_row.id, platform=response_row.platform)
    local_log_ctx.debug("Starting LLM extraction for response")

    system_prompt = build_extraction_prompt(
        brand_name=brand_name,
        competitor_names=competitor_names,
        platform=response_row.platform,
        query_intent=response_row.query_intent,
        query_text=response_row.query_text,
        response_text=response_row.response_text,
    )

    try:
        extraction_result: LLMExtractionResult = await extract_competitor_data_with_llm(
            system_prompt=system_prompt,
            user_prompt="Extract competitor and brand mentions as JSON.",
            log_ctx=local_log_ctx,
        )
    except Exception as e:
        local_log_ctx.error("LLM extraction failed for response", error=str(e))
        return [], None

    competitor_mentions: List[CompetitorMention] = []
    for comp_ext in extraction_result.competitors_found:
        # Fuzzy match competitor name to ensure it's one of the known competitors
        # using a higher threshold for more accurate matching.
        if competitor_names:
            match = process.extractOne(comp_ext.name, competitor_names, scorer=fuzz.token_set_ratio, score_cutoff=80)
            if match:
                matched_competitor_name = match[0]
            else:
                local_log_ctx.warning(
                    "Extracted competitor name did not match known competitors closely enough",
                    extracted_name=comp_ext.name,
                    known_competitors=competitor_names
                )
                continue
        else:
            # If no known competitors, we can't validate the extracted name.
            # For now, we will skip if no known competitors are provided.
            local_log_ctx.warning("No known competitors provided, skipping competitor mention extraction.")
            continue

        competitor_mentions.append(
            CompetitorMention(
                competitor_name=matched_competitor_name,
                platform=response_row.platform,
                response_id=response_row.id,
                query_intent=response_row.query_intent,
                mention_position=comp_ext.position,
                is_recommended_first=comp_ext.is_recommended_first,
                sentiment=comp_ext.sentiment,
                comparative_language=comp_ext.comparative_snippet,
            )
        )
    
    brand_mention: Optional[BrandMentionExtraction] = None
    if extraction_result.brand_mention.mentioned:
        brand_mention = BrandMentionExtraction(
            mentioned=True,
            position=extraction_result.brand_mention.position,
            is_recommended_first=extraction_result.brand_mention.is_recommended_first,
            sentiment=extraction_result.brand_mention.sentiment,
            comparative_snippet=extraction_result.brand_mention.comparative_snippet,
        )
        # Attach platform information to brand mention for aggregation
        # This is a temporary measure for aggregation, not part of the core model
        setattr(brand_mention, 'platform', response_row.platform)

    local_log_ctx.debug(
        "Finished LLM extraction for response",
        num_competitor_mentions=len(competitor_mentions),
        brand_mentioned=brand_mention is not None,
    )

    return competitor_mentions, brand_mention
