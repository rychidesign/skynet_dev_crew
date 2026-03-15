import json
import structlog
from supabase._async.client import AsyncClient

logger = structlog.get_logger(__name__)

# Pricing per 1 Million tokens (Input, Output) in USD
MODEL_PRICING = {
    "gpt-4o": {"input": 5.0, "output": 15.0},
    "gpt-4-turbo": {"input": 10.0, "output": 30.0},
    "claude-3-5-sonnet-20240620": {"input": 3.0, "output": 15.0},
    "perplexity-sonar": {"input": 0.2, "output": 0.2}, 
    "gemini-1.5-pro": {"input": 3.5, "output": 10.5},
    "copilot": {"input": 0.0, "output": 0.0} # Needs real MS pricing if directly used
}

def calculate_cost(model_id: str, input_tokens: int, output_tokens: int) -> float:
    """
    Computes the total USD cost for a given API call based on token usage.
    Returns 0.0 and logs a warning if the model pricing is unknown.
    """
    pricing = MODEL_PRICING.get(model_id)
    if not pricing:
        logger.warning(f"Cost Tracker: Unknown model '{model_id}', assuming 0 cost.")
        return 0.0
        
    cost_input = (input_tokens / 1_000_000.0) * pricing["input"]
    cost_output = (output_tokens / 1_000_000.0) * pricing["output"]
    total_cost = cost_input + cost_output
    
    return round(total_cost, 6)

async def log_api_call(
    db: AsyncClient, 
    audit_id: str, 
    agent: str, 
    platform: str, 
    model_id: str, 
    input_tokens: int, 
    output_tokens: int, 
    latency_ms: int
) -> None:
    """
    Calculates cost and logs the LLM interaction into the 'audit_events' table.
    Fails gracefully (only logging via structlog) to avoid breaking the main pipeline.
    """
    cost_usd = calculate_cost(model_id, input_tokens, output_tokens)
    
    metadata = {
        "agent": agent,
        "platform": platform,
        "model_id": model_id,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "latency_ms": latency_ms,
        "cost_usd": cost_usd
    }
    
    try:
        response = await db.table("audit_events").insert({
            "audit_id": audit_id,
            "event_type": "api_call",
            "severity": "info",
            "message": f"Called {platform} ({model_id}) - Cost: ${cost_usd:.6f}",
            "metadata": metadata
        }).execute()
        
        if not response.data:
            logger.error("Failed to insert audit_event, no data returned", audit_id=audit_id)
            
    except Exception as e:
        logger.error(
            "Failed to log API call to Supabase", 
            audit_id=audit_id, 
            error=str(e), 
            exc_info=True, 
            metadata=metadata
        )
