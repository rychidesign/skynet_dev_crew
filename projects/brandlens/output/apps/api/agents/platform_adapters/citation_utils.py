import re
from typing import List
from urllib.parse import urlparse

from models.audit import CitationItem # Import CitationItem from models.audit

# Regex patterns for citation extraction
BARE_URL_PATTERN = re.compile(r'(https?://[^\s\])\"]+|www\.[^\s\])\"]+)')
MARKDOWN_LINK_PATTERN = re.compile(r'\\[([^\]]+)\\]\\((https?://[^)]+)\\)')
# This pattern is specifically for domain mentions that are not part of a full URL
DOMAIN_ONLY_PATTERN = re.compile(r'\b(?P<domain_only>[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b')

def _get_domain_from_url(url: str) -> str:
    try:
        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        if domain.startswith("www."):
            domain = domain[4:]
        return domain.lower()
    except Exception:
        return "unknown"

def extract_citations(text: str, company_domain: str) -> List[CitationItem]:
    found_citations: List[CitationItem] = []
    unique_urls = set() # To avoid duplicate citations

    # 1. Extract markdown links
    for match in MARKDOWN_LINK_PATTERN.finditer(text):
        title = match.group(1)
        url = match.group(2)
        domain = _get_domain_from_url(url)
        if url not in unique_urls:
            is_brand_citation = company_domain.lower() in domain.lower() if company_domain else False
            found_citations.append(CitationItem(
                url=url,
                domain=domain,
                title=title,
                type="direct_url",
                is_brand_citation=is_brand_citation,
            ))
            unique_urls.add(url)

    # 2. Extract bare URLs (if not already found in markdown links)
    for match in BARE_URL_PATTERN.finditer(text):
        url = match.group(0).strip('[]\') # Remove potential brackets
        domain = _get_domain_from_url(url)
        if url not in unique_urls:
            is_brand_citation = company_domain.lower() in domain.lower() if company_domain else False
            found_citations.append(CitationItem(
                url=url,
                domain=domain,
                title=url,
                type="direct_url",
                is_brand_citation=is_brand_citation,
            ))
            unique_urls.add(url)
    
    # 3. Extract domain-only mentions (if not part of a URL or already covered by direct_url)
    for match in DOMAIN_ONLY_PATTERN.finditer(text):
        domain_only = match.group('domain_only').lower()
        # Check if this domain_only is already part of a direct_url citation
        is_already_direct_url = any(domain_only in c.domain for c in found_citations if c.type == "direct_url")
        
        if not is_already_direct_url:
            # Simulate a URL for domain-only mentions to ensure uniqueness and proper structure
            simulated_url = f"https://{domain_only}"
            if simulated_url not in unique_urls: # Check if a full URL for this domain was already added
                is_brand_citation = company_domain.lower() in domain_only if company_domain else False
                found_citations.append(CitationItem(
                    url=simulated_url,
                    domain=domain_only,
                    title=domain_only,
                    type="domain_mention",
                    is_brand_citation=is_brand_citation,
                ))
                unique_urls.add(simulated_url)

    return found_citations