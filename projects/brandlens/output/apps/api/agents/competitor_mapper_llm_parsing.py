from typing import List, Optional, Dict, Any, Tuple
import json
import logging

from apps.api.agents.competitor_mapper_constants_and_types import CompetitorMentionResult, FilteredResponse

log = logging.getLogger(__name__)

def parse_llm_output(
    raw_text: str,
    response_id: str,
    audit_id: str,
    competitors: List[str],
    log_ctx: logging.Logger,
) -> List[CompetitorMentionResult]:
    """
    Parses LLM JSON, validates fields, returns List[CompetitorMentionResult].
    """
    try:
        data = json.loads(raw_text)
        mentions_data = data.get("competitor_mentions", [])
        parsed_mentions: List[CompetitorMentionResult] = []

        for mention in mentions_data:
            competitor_name = mention.get("competitor_name")
            if not competitor_name or competitor_name not in competitors:
                log_ctx.warning(
                    "LLM returned invalid competitor name or one not in list",
                    raw_name=competitor_name,
                    response_id=response_id,
                    audit_id=audit_id,
                )
                continue

            sentiment = mention.get("comparison_sentiment")
            if sentiment not in ["positive", "negative", "neutral"]:
                log_ctx.warning(
                    "LLM returned invalid comparison_sentiment",
                    sentiment=sentiment,
                    competitor_name=competitor_name,
                    response_id=response_id,
                    audit_id=audit_id,
                )
                sentiment = "neutral" # Default to neutral

            # Ensure types are correct
            position_rank = mention.get("position_rank")
            if position_rank is not None:
                try:
                    position_rank = int(position_rank)
                except (ValueError, TypeError):
                    position_rank = None

            is_recommended = mention.get("is_recommended", False)
            if not isinstance(is_recommended, bool):
                is_recommended = False

            mention_count = mention.get("mention_count", 0)
            if not isinstance(mention_count, int):
                mention_count = 0

            parsed_mentions.append(
                CompetitorMentionResult(
                    competitor_name=competitor_name,
                    position_rank=position_rank,
                    is_recommended=is_recommended,
                    comparison_sentiment=sentiment,
                    mention_count=mention_count,
                )
            )
        return parsed_mentions
    except json.JSONDecodeError as e:
        log_ctx.error(
            "LLM returned malformed JSON",
            error=str(e),
            raw_text=raw_text,
            response_id=response_id,
            audit_id=audit_id,
        )
        return []
    except Exception as e:
        log_ctx.error(
            "Error parsing LLM output",
            error=str(e),
            raw_text=raw_text,
            response_id=response_id,
            audit_id=audit_id,
        )
        return []
