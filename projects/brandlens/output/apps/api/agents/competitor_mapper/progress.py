from typing import Any, Dict, Optional
import structlog
from apps.api.core.state import AuditState

log = structlog.get_logger(__name__)

def update_competitor_mapper_progress(
    state: AuditState,
    total_responses: int,
    processed_responses: int,
    log_ctx: structlog.BoundLogger,
) -> AuditState:
    """
    Updates the progress for the competitor mapper agent in the audit state.
    """
    progress_percent = int((processed_responses / total_responses) * 100) if total_responses > 0 else 0
    
    current_progress = state.get("current_progress", {})
    current_progress["competitor_mapper"] = {
        "status": "running",
        "progress": progress_percent,
        "detail": f"Processed {processed_responses}/{total_responses} responses",
    }
    log_ctx.debug("Updated competitor mapper progress", progress=progress_percent)
    return state.update_progress("competitor_mapper", progress_percent, f"Processed {processed_responses}/{total_responses} responses")

def mark_competitor_mapper_complete(
    state: AuditState,
    log_ctx: structlog.BoundLogger,
) -> AuditState:
    """
    Marks the competitor mapper agent as complete in the audit state.
    """
    log_ctx.info("Competitor mapper agent completed")
    return state.update_progress("competitor_mapper", 100, "Competitor analysis complete", "completed")

def mark_competitor_mapper_failed(
    state: AuditState,
    error_message: str,
    log_ctx: structlog.BoundLogger,
) -> AuditState:
    """
    Marks the competitor mapper agent as failed in the audit state.
    """
    log_ctx.error("Competitor mapper agent failed", error=error_message)
    return state.update_progress("competitor_mapper", 0, f"Failed: {error_message}", "failed")
