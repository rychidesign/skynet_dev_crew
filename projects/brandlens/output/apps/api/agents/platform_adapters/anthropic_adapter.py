import httpx
import structlog
import time

from core.config import settings
from agents.platform_adapters import PlatformAdapterResult, RateLimitError
from models.audit import CitationItem, RAGSourceItem
from agents.platform_adapters.citation_utils import extract_citations

log = structlog.get_logger()

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_API_VERSION = "2023-06-01"
REQUEST_TIMEOUT_SECONDS = 30
ANTHROPIC_SYSTEM_PROMPT = (
    "You are a neutral research assistant. Answer the following question "
    "factually and objectively. Do not use promotional language. "
    "Include source URLs where possible."
)

class AnthropicAdapter:
    def __init__(self):
        self.api_key = settings.ANTHROPIC_API_KEY
        self.model = settings.ANTHROPIC_MODEL

    async def call(self, query_text: str, company_name: str, company_domain: str) -> PlatformAdapterResult:
        start_time = time.monotonic()
        
        messages = [
            {"role": "user", "content": query_text},
        ]

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": ANTHROPIC_API_VERSION,
            "content-type": "application/json"
        }
        payload = {
            "model": self.model,
            "max_tokens": 1024, # Max tokens for the response
            "system": ANTHROPIC_SYSTEM_PROMPT,
            "messages": messages
        }

        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
                response = await client.post(ANTHROPIC_API_URL, headers=headers, json=payload)
                response.raise_for_status()
            data = response.json()

            response_text = "".join([block['text'] for block in data['content'] if block['type'] == 'text'])
            input_tokens = data['usage']['input_tokens']
            output_tokens = data['usage']['output_tokens']
            
            citations = extract_citations(response_text, company_domain)
            rag_sources: List[RAGSourceItem] = [] # Anthropic doesn't expose retrieval sources in base API

            latency_ms = int((time.monotonic() - start_time) * 1000)

            log.info("Anthropic API call successful", model=self.model, input_tokens=input_tokens, output_tokens=output_tokens, latency_ms=latency_ms)

            return PlatformAdapterResult(
                response_text=response_text,
                citations=citations,
                rag_sources=rag_sources,
                model_id=self.model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
            )

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                retry_after_str = e.response.headers.get("Retry-After", "0")
                try:
                    retry_after = float(retry_after_str)
                except ValueError:
                    retry_after = 5.0 # Default if header is malformed
                log.warning("Anthropic rate limit hit", retry_after=retry_after, exc_info=True)
                raise RateLimitError(retry_after_seconds=retry_after)
            log.error("Anthropic API HTTP error", status_code=e.response.status_code, detail=e.response.text, exc_info=True)
            raise # Re-raise for tenacity to handle
        except (httpx.RequestError, httpx.TimeoutException) as e:
            log.error("Anthropic API request failed or timed out", exc_info=True)
            raise # Re-raise for tenacity to handle