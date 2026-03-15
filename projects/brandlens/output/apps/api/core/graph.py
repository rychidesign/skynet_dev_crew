import asyncio
import structlog
from typing import Any
from langgraph.graph import StateGraph, START, END

from core.state import AuditState, AgentMessage

logger = structlog.get_logger(__name__)

# --- STUB AGENTS (until properly implemented in Task 5.3 - 5.9) ---

async def stub_preprocessor(state: AuditState) -> AuditState:
    logger.info("Executing preprocessor", audit_id=state.audit_id)
    return AuditState(
        **{**state.__dict__, "messages": [AgentMessage(agent="preprocessor", content="Completed processing")]}
    )

async def stub_query_generator(state: AuditState) -> AuditState:
    logger.info("Executing query_generator", audit_id=state.audit_id)
    return AuditState(
        **{**state.__dict__, "messages": [AgentMessage(agent="query_generator", content="Generated queries")]}
    )

async def stub_response_collector(state: AuditState) -> AuditState:
    logger.info("Executing response_collector", audit_id=state.audit_id)
    return AuditState(
        **{**state.__dict__, "messages": [AgentMessage(agent="response_collector", content="Collected responses")]}
    )

async def stub_mention_analyzer(state: AuditState) -> AuditState:
    logger.info("Executing mention_analyzer", audit_id=state.audit_id)
    return AuditState(
        **{**state.__dict__, "messages": [AgentMessage(agent="mention_analyzer", content="Analyzed mentions")]}
    )

async def stub_competitor_mapper(state: AuditState) -> AuditState:
    logger.info("Executing competitor_mapper", audit_id=state.audit_id)
    return AuditState(
        **{**state.__dict__, "messages": [AgentMessage(agent="competitor_mapper", content="Mapped competitors")]}
    )

async def stub_synthesizer(state: AuditState) -> AuditState:
    logger.info("Executing synthesizer", audit_id=state.audit_id)
    return AuditState(
        **{**state.__dict__, "messages": [AgentMessage(agent="synthesizer", content="Synthesized final report")]}
    )

# Try importing real agents, fallback to stubs if not implemented yet
try:
    from agents.preprocessor import run as preprocessor_node
except ImportError:
    preprocessor_node = stub_preprocessor

try:
    from agents.query_generator import run as query_generator_node
except ImportError:
    query_generator_node = stub_query_generator

try:
    from agents.response_collector import run as response_collector_node
except ImportError:
    response_collector_node = stub_response_collector

try:
    from agents.mention_analyzer import run as mention_analyzer_node
except ImportError:
    mention_analyzer_node = stub_mention_analyzer

try:
    from agents.competitor_mapper import run as competitor_mapper_node
except ImportError:
    competitor_mapper_node = stub_competitor_mapper

try:
    from agents.synthesizer import run as synthesizer_node
except ImportError:
    synthesizer_node = stub_synthesizer


# --- GRAPH ASSEMBLY ---

# 1. Initialize StateGraph with the schema
workflow = StateGraph(AuditState)

# 2. Add nodes (the agents)
workflow.add_node("preprocessor", preprocessor_node)
workflow.add_node("query_generator", query_generator_node)
workflow.add_node("response_collector", response_collector_node)
workflow.add_node("mention_analyzer", mention_analyzer_node)
workflow.add_node("competitor_mapper", competitor_mapper_node)
workflow.add_node("synthesizer", synthesizer_node)

# 3. Define the edges (the workflow)
workflow.add_edge(START, "preprocessor")
workflow.add_edge("preprocessor", "query_generator")
workflow.add_edge("query_generator", "response_collector")

# Parallel branches: Response Collector branches out to both
workflow.add_edge("response_collector", "mention_analyzer")
workflow.add_edge("response_collector", "competitor_mapper")

# Converge back to synthesizer
workflow.add_edge("mention_analyzer", "synthesizer")
workflow.add_edge("competitor_mapper", "synthesizer")

# Finish
workflow.add_edge("synthesizer", END)

# 4. Compile the graph
audit_graph = workflow.compile()

async def run_audit_pipeline(initial_state: AuditState) -> AuditState | None:
    """
    Entry point to trigger the background LangGraph audit pipeline.
    Expects a fully populated initial AuditState (with 'pending' status).
    """
    log = logger.bind(audit_id=initial_state.audit_id, company_id=initial_state.company_id)
    log.info("Starting audit pipeline")
    
    try:
        # LangGraph invoke returns the final state dict or updated dict
        final_state_dict = await audit_graph.ainvoke(initial_state)
        log.info("Audit pipeline completed successfully", status=final_state_dict.get("status", "unknown"))
        return final_state_dict
    except Exception as e:
        log.error("Audit pipeline failed", error=str(e), exc_info=True)
        # Update the state with error if something fails fundamentally
        initial_state.status = "failed"
        initial_state.error = str(e)
        return initial_state
