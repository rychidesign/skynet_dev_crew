from dataclasses import dataclass, field
from typing import Annotated, List, Optional, Dict, Any
from pydantic import BaseModel, Field

class AgentMessage(BaseModel):
    """
    Message structure for communication and logging between LangGraph agents.
    """
    agent: str
    content: str
    metadata: dict = Field(default_factory=dict)

def add_messages(left: list[AgentMessage], right: list[AgentMessage]) -> list[AgentMessage]:
    """
    Reducer function for LangGraph to append new messages to the state array.
    """
    return left + right

@dataclass
class AuditState:
    """
    State object flowing through the LangGraph audit pipeline.
    Agents receive this state, modify it, and return the updated version.
    """
    audit_id: str
    company_id: str
    organization_id: str
    config: dict
    status: str
    messages: Annotated[list[AgentMessage], add_messages] = field(default_factory=list)
    error: str | None = None
    
    # Fields for Agent 4: Competitor Mapper
    competitor_results: List[Dict[str, Any]] = field(default_factory=list)
    brand_competitive_stats: Optional[Dict[str, Any]] = None

    # Common progress tracking
    current_progress: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def update_progress(self, agent_name: str, progress_percent: int, detail_message: str, status: str = "running") -> 'AuditState':
        if "current_progress" not in self.__dict__:
            self.current_progress = {}

        self.current_progress[agent_name] = {
            "status": status,
            "progress": progress_percent,
            "detail": detail_message,
        }
        return self
