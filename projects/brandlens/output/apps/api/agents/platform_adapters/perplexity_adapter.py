import httpx
import structlog
import time
from typing import List, Dict, Any

from core.config import settings
from agents.platform_adapters import PlatformAdapterResult, RateLimitError
from models.audit import CitationItem, RAGSourceItem
from agents.platform_adapters.citation_utils import extract_citations, _get_domain_from_url

log = structlog.get_logger()

PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"
REQUEST_TIMEOUT_SECONDS = 30
PERPLEXITY_SYSTEM_PROMPT = (
    "You are a neutral research assistant. Answer the following question "
    "factually and objectively. Do not use promotional language. "
    "Include source URLs where possible."
)

class PerplexityAdapter:
    def __init__(self):
        self.api_key = settings.PERPLEXITY_API_KEY
        self.model = settings.PERPLEXITY_MODEL

    async def call(self, query_text: str, company_name: str, company_domain: str) -> PlatformAdapterResult:
        start_time = time.monotonic()
        
        messages = [
            {"role": "system", "content": PERPLEXITY_SYSTEM_PROMPT},
            {"role": "user", "content": query_text},
        ]

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": 1024,
            "temperature": 0.3,
            "return_citations": True,
            "return_images": False,
        }

        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
                response = await client.post(PERPLEXITY_API_URL, headers=headers, json=payload)
                response.raise_for_status()
            data = response.json()

            response_text = data['choices'][0]['message']['content']
            input_tokens = data['usage']['prompt_tokens']
            output_tokens = data['usage']['completion_tokens']
            
            # Perplexity provides structured citations in the response, which we'll map to RAG sources
            perplexity_raw_citations = data.get('citations', [])
            rag_sources = self._process_perplexity_rag_sources(perplexity_raw_citations, company_domain)

            # Also extract citations from the response text using the utility function
            text_extracted_citations = extract_citations(response_text, company_domain)
            
            # Combine text-extracted citations with Perplexity's own structured citations
            all_citations: List[CitationItem] = list(text_extracted_citations)
            # Use a set to track unique URLs for deduplication from structured citations
            unique_urls_in_all_citations = {c.url for c in all_citations}

            for p_citation in perplexity_raw_citations:
                url = p_citation.get("url")
                # Only add if URL is new to avoid duplicates
                if url and url not in unique_urls_in_all_citations:
                    domain = _get_domain_from_url(url) if url else "unknown"
                    is_brand_citation = company_domain.lower() in domain.lower() if company_domain else False
                    all_citations.append(CitationItem(
                        url=url,
                        domain=domain,
                        title=p_citation.get("title", url), # Perplexity might provide a title
                        type="rag_source", # Specific type for Perplexity's structured citations
                        is_brand_citation=is_brand_citation,
                    ))
                    unique_urls_in_all_citations.add(url)

            latency_ms = int((time.monotonic() - start_time) * 1000)

            log.info("Perplexity API call successful", model=self.model, input_tokens=input_tokens, output_tokens=output_tokens, latency_ms=latency_ms)

            return PlatformAdapterResult(
                response_text=response_text,
                citations=all_citations,
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
                log.warning("Perplexity rate limit hit", retry_after=retry_after, exc_info=True)
                raise RateLimitError(retry_after_seconds=retry_after)
            log.error("Perplexity API HTTP error", status_code=e.response.status_code, detail=e.response.text, exc_info=True)
            raise # Re-raise for tenacity to handle
        except (httpx.RequestError, httpx.TimeoutException) as e:
            log.error("Perplexity API request failed or timed out", exc_info=True)
            raise # Re-raise for tenacity to handle

    def _process_perplexity_rag_sources(self, perplexity_citations: List[Dict], company_domain: str) -> List[RAGSourceItem]:
        rag_sources = []
        for citation in perplexity_citations:
            url = citation.get("url")
            domain = _get_domain_from_url(url) if url else "unknown"
            is_brand_source = company_domain.lower() in domain.lower() if company_domain else False
            rag_sources.append(RAGSourceItem(
                url=url,
                domain=domain,
                title=citation.get("title", url), # Perplexity might provide a title
                snippet=citation.get("snippet", ""), # Perplexity often provides a snippet
                is_brand_source=is_brand_source,
            ))
        return rag_sources