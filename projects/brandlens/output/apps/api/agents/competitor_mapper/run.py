import asyncio
from typing import List, Tuple, Dict, Any
import structlog
from supabase._async.client import AsyncClient

from apps.api.core.state import AuditState
from apps.api.agents.competitor_mapper.models import (
    CompetitorMention,
    BrandMentionExtraction,
    CompetitorStats,
    BrandCompetitiveStats,
    ResponseRow,
)
from apps.api.agents.competitor_mapper.db_ops import (
    fetch_comparative_responses,
    fetch_competitor_list,
    upsert_audit_competitors,
)
from apps.api.agents.competitor_mapper.extractor import extract_mentions_for_response
from apps.api.agents.competitor_mapper.aggregator import aggregate_competitor_stats
from apps.api.agents.competitor_mapper.progress import (
    update_competitor_mapper_progress,
    mark_competitor_mapper_complete,
    mark_competitor_mapper_failed,
)

log = structlog.get_logger(__name__)

async def run(
    state: AuditState,
    db: AsyncClient, # Inject db client
) -> AuditState:
    """
    Competitor Mapper Agent: Orchestrates extraction and aggregation of competitor data.
    """
    audit_id = state.audit_id
    company_id = state.company_id
    log_ctx = log.bind(audit_id=audit_id, agent="competitor_mapper")
    log_ctx.info("Competitor Mapper agent started")

    try:
        # 1. Fetch comparative/recommendation intent responses
        response_rows: List[Dict] = await fetch_comparative_responses(db, audit_id, log_ctx)
        total_responses = len(response_rows)
        if not response_rows:
            log_ctx.info("No comparative or recommendation responses found for audit.")
            return mark_competitor_mapper_complete(state, log_ctx)

        # 2. Fetch company brand name and competitors
        competitor_names, brand_name, competitor_domains = await fetch_competitor_list(db, company_id, log_ctx)
        if not competitor_names:
            log_ctx.warning("No competitors defined for company. Skipping detailed competitor analysis.")
            # We still need to process for brand mentions and aggregate them

        all_competitor_mentions: List[CompetitorMention] = []
        all_brand_mentions: List[BrandMentionExtraction] = []
        processed_count = 0

        # Concurrently extract mentions for all responses
        extraction_tasks = []
        for row_dict in response_rows:
            row = ResponseRow(**row_dict)
            extraction_tasks.append(
                extract_mentions_for_response(row, brand_name, competitor_names, log_ctx)
            )
        
        for future in asyncio.as_completed(extraction_tasks):
            competitor_mentions, brand_mention = await future
            all_competitor_mentions.extend(competitor_mentions)
            if brand_mention:
                all_brand_mentions.append(brand_mention)
            processed_count += 1
            state = update_competitor_mapper_progress(state, total_responses, processed_count, log_ctx)

        log_ctx.info(
            "Finished LLM extractions for all responses",
            total_responses=total_responses,
            extracted_competitor_mentions=len(all_competitor_mentions),
            extracted_brand_mentions=len(all_brand_mentions),
        )

        # 3. Aggregate results
        competitor_stats, brand_competitive_stats = aggregate_competitor_stats(
            all_competitor_mentions=all_competitor_mentions,
            all_brand_mentions=all_brand_mentions,
            competitor_names=competitor_names,
            competitor_domains=competitor_domains,
            brand_name=brand_name,
            total_comparative_responses=total_responses,
        )

        # 4. Upsert aggregated competitor stats to DB
        await upsert_audit_competitors(db, audit_id, competitor_stats, log_ctx)

        # 5. Store results in AuditState
        state.competitor_results = [cs.model_dump() for cs in competitor_stats] # Store as dicts
        state.brand_competitive_stats = brand_competitive_stats.model_dump() # Store as dict

        return mark_competitor_mapper_complete(state, log_ctx)

    except Exception as e:
        log_ctx.error("Competitor Mapper agent failed unexpectedly", error=str(e))
        return mark_competitor_mapper_failed(state, str(e), log_ctx)
