import httpx
import structlog
import time

from core.config import settings
from agents.platform_adapters import PlatformAdapterResult, RateLimitError
from models.audit import CitationItem, RAGSourceItem
from agents.platform_adapters.citation_utils import extract_citations

log = structlog.get_logger()

OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
REQUEST_TIMEOUT_SECONDS = 30
OPENAI_SYSTEM_PROMPT = (
    "You are a neutral research assistant. Answer the following question "
    "factually and objectively. Do not use promotional language. "
    "Include source URLs where possible."
)

class OpenAIAdapter:
    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        self.model = settings.OPENAI_MODEL

    async def call(self, query_text: str, company_name: str, company_domain: str) -> PlatformAdapterResult:
        start_time = time.monotonic()
        
        messages = [
            {"role": "system", "content": OPENAI_SYSTEM_PROMPT},
            {"role": "user", "content": query_text},
        ]

        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {"model": self.model, "messages": messages, "max_tokens": 1024, "temperature": 0.3}

        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
                response = await client.post(OPENAI_API_URL, headers=headers, json=payload)
                response.raise_for_status()
            data = response.json()

            response_text = data['choices'][0]['message']['content']
            input_tokens = data['usage']['prompt_tokens']
            output_tokens = data['usage']['completion_tokens']
            
            citations = extract_citations(response_text, company_domain)
            rag_sources: List[RAGSourceItem] = [] # OpenAI doesn't expose retrieval sources

            latency_ms = int((time.monotonic() - start_time) * 1000)

            log.info("OpenAI API call successful", model=self.model, input_tokens=input_tokens, output_tokens=output_tokens, latency_ms=latency_ms)

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
                log.warning("OpenAI rate limit hit", retry_after=retry_after, exc_info=True)
                raise RateLimitError(retry_after_seconds=retry_after)
            log.error("OpenAI API HTTP error", status_code=e.response.status_code, detail=e.response.text, exc_info=True)
            raise # Re-raise for tenacity to handle
        except (httpx.RequestError, httpx.TimeoutException) as e:
            log.error("OpenAI API request failed or timed out", exc_info=True)
            raise # Re-raise for tenacity to handle