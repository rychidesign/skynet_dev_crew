from typing import Protocol, Dict, Type, List
from pydantic import BaseModel
from models.audit import CitationItem, RAGSourceItem

class RateLimitError(Exception):
    """Custom exception for rate limiting, with retry_after_seconds."""
    def __init__(self, retry_after_seconds: float = 5.0) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__(f"Rate limited; retry after {retry_after_seconds}s")

class PlatformAdapterResult(BaseModel):
    response_text: str
    citations: List[CitationItem]
    rag_sources: List[RAGSourceItem]
    model_id: str
    input_tokens: int
    output_tokens: int
    latency_ms: int

class PlatformAdapter(Protocol):
    async def call(
        self,
        query_text: str,
        company_name: str,
        company_domain: str,
    ) -> PlatformAdapterResult:
        ...


def get_adapter(platform: str) -> PlatformAdapter:
    if platform == "chatgpt":
        from .openai_adapter import OpenAIAdapter
        return OpenAIAdapter()
    elif platform == "claude":
        from .anthropic_adapter import AnthropicAdapter
        return AnthropicAdapter()
    elif platform == "perplexity":
        from .perplexity_adapter import PerplexityAdapter
        return PerplexityAdapter()
    elif platform in ("google_aio", "copilot"):
        raise NotImplementedError(f"Adapter for '{platform}' not yet implemented")
    else:
        raise ValueError(f"Unknown platform: '{platform}'")