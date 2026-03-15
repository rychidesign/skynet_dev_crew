"""Preprocessor Agent for GEO audit pipeline."""
import asyncio
from datetime import datetime, timezone
import httpx
import structlog
from urllib.parse import urljoin, urlparse

from supabase._async.client import AsyncClient, create_client

from apps.api.core.state import AuditState, AgentMessage
from apps.api.core.config import settings
from apps.api.core.utils.robots_parser import (
    AI_BOTS,
    parse_robots_txt,
    extract_sitemap_urls_from_robots,
)
from apps.api.core.utils.sitemap_parser import (
    fetch_and_parse_sitemap,
    calculate_freshness_metrics,
)
from apps.api.core.utils.http_checker import check_url_status

log = structlog.get_logger(__name__)


async def get_supabase_client() -> AsyncClient:
    """Returns a Supabase AsyncClient bypassing RLS."""
    return await create_client(
        settings.SUPABASE_URL,
        settings.SUPABASE_SERVICE_ROLE_KEY
    )


async def run(state: AuditState) -> AuditState:
    """
    Preprocessor Agent Stage 1:
    Gathers technical and metadata facts about the company's domain.
    """
    logger = log.bind(audit_id=state.audit_id, agent="preprocessor")
    logger.info("Preprocessor agent started")
    
    supabase = await get_supabase_client()
    
    # 1. Log audit started event
    try:
        await supabase.table("audit_events").insert({
            "audit_id": state.audit_id,
            "type": "stage_started",
            "message": "Preprocessor agent started collecting technical facts."
        }).execute()
    except Exception as e:
        logger.warning(f"Failed to log audit event: {e}")

    # 2. Get company domain
    try:
        res = await supabase.table("companies").select("domain").eq("id", state.company_id).single().execute()
        domain = res.data.get("domain")
        if not domain:
            raise ValueError("Company domain is missing.")
    except Exception as e:
        logger.error(f"Failed to fetch domain for company {state.company_id}: {e}")
        try:
            await supabase.table("audit_technical_checks").insert({
                "audit_id": state.audit_id,
                "sitemap_present": False,
                "sitemap_valid": False,
            }).execute()
        except Exception:
            pass
        
        state.error = f"Failed to retrieve company domain: {e}"
        state.messages.append(AgentMessage(agent="preprocessor", content="Failed to get domain.", metadata={"error": str(e)}))
        return state

    domain = domain.strip().lower()
    if not domain.startswith("http"):
        base_url = f"https://{domain}"
    else:
        base_url = domain
        domain = urlparse(domain).netloc

    # Initialize variables
    robots_content: str | None = None
    crawler_permissions = {bot: "allowed" for bot in AI_BOTS}
    sitemap_present = False
    sitemap_valid = False
    sitemap_urls: list[str] = []
    lastmods: list[datetime] = []
    
    # Use default SSL verification (verify=True is default in httpx) - SECURITY FIX
    async with httpx.AsyncClient(follow_redirects=True) as client:
        # 3. Process robots.txt
        robots_url = urljoin(base_url, "/robots.txt")
        try:
            resp = await client.get(robots_url, timeout=10.0)
            if resp.status_code == 200:
                robots_content = resp.text
                crawler_permissions = parse_robots_txt(robots_content)
        except Exception as e:
            logger.warning(f"Failed to fetch robots.txt at {robots_url}: {e}")

        # 4. Process sitemap.xml
        sitemap_locations: list[str] = []
        if robots_content:
            sitemap_locations.extend(extract_sitemap_urls_from_robots(robots_content))
             
        if not sitemap_locations:
            sitemap_locations.append(urljoin(base_url, "/sitemap.xml"))
            
        for s_url in sitemap_locations:
            s_present, s_valid, s_urls, s_lastmods = await fetch_and_parse_sitemap(s_url, client)
            if s_present:
                sitemap_present = True
                sitemap_valid = s_valid
                sitemap_urls = s_urls
                lastmods = s_lastmods
                break  # Found a valid sitemap, stop searching

        # 5. Calculate Freshness Metrics (GEO-11)
        avg_lastmod_days, current_year_pct, update_frequency_monthly = calculate_freshness_metrics(lastmods)

        # 6. HTTP Status Checks (Crawl Accessibility - GEO-17)
        urls_to_check = sitemap_urls[:10] if sitemap_urls else [base_url]
        http_check_results: list[dict] = []
        if urls_to_check:
            tasks = [check_url_status(url, client) for url in urls_to_check]
            http_check_results = await asyncio.gather(*tasks)

    # 7. Save to database
    technical_check_data = {
        "audit_id": state.audit_id,
        "robots_txt_raw": robots_content,
        "crawler_permissions": crawler_permissions,
        "sitemap_present": sitemap_present,
        "sitemap_valid": sitemap_valid,
        "sitemap_url_count": len(sitemap_urls),
        "sampled_pages": http_check_results,
        "avg_lastmod_days": avg_lastmod_days,
        "update_frequency_monthly": update_frequency_monthly,
        "current_year_content_pct": current_year_pct,
        "sitemap_sample": sitemap_urls[:10] if sitemap_urls else []
    }

    try:
        await supabase.table("audit_technical_checks").insert(technical_check_data).execute()
        
        await supabase.table("audit_events").insert({
            "audit_id": state.audit_id,
            "type": "stage_completed",
            "message": "Preprocessor agent completed successfully."
        }).execute()
         
    except Exception as e:
        logger.error(f"Failed to insert technical checks to database: {e}")
        state.error = f"Database insertion error: {e}"
        state.messages.append(AgentMessage(agent="preprocessor", content="Failed to save data.", metadata={"error": str(e)}))
        return state

    # Append success message
    msg = AgentMessage(
        agent="preprocessor",
        content="Technical checks completed.",
        metadata={
            "sitemap_present": sitemap_present,
            "sitemap_urls": len(sitemap_urls),
            "crawlers_allowed": sum(1 for v in crawler_permissions.values() if v == "allowed")
        }
    )
    state.messages.append(msg)
    
    logger.info("Preprocessor agent completed successfully")
    return state
