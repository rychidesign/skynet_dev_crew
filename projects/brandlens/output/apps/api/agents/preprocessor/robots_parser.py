"""robots.txt fetcher and parser for AI crawler permissions."""
import structlog
import httpx

from models.technical_check import CrawlerPermission, RobotsAnalysis

logger = structlog.get_logger(__name__)

AI_CRAWLERS = ["GPTBot", "ClaudeBot", "Google-Extended", "bingbot", "Googlebot"]


async def fetch_robots_txt(domain: str, client: httpx.AsyncClient) -> str | None:
    """Fetch robots.txt from https://{domain}/robots.txt. Returns raw content or None."""
    url = f"https://{domain}/robots.txt"
    try:
        response = await client.get(url, timeout=10.0)
        if response.status_code == 200:
            return response.text
        return None
    except httpx.TimeoutException:
        logger.warning("robots.txt fetch timed out", domain=domain)
        return None
    except httpx.RequestError as exc:
        logger.warning("robots.txt fetch failed", domain=domain, error=str(exc))
        return None


def _parse_blocks(content: str) -> list[tuple[list[str], list[str], list[str]]]:
    """Parse robots.txt into (agents, disallows, allows) blocks."""
    blocks: list[tuple[list[str], list[str], list[str]]] = []
    agents: list[str] = []
    disallows: list[str] = []
    allows: list[str] = []

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            if agents:
                blocks.append((agents[:], disallows[:], allows[:]))
                agents, disallows, allows = [], [], []
            continue
        if ":" not in line:
            continue
        field, _, value = line.partition(":")
        field, value = field.strip().lower(), value.strip()
        if field == "user-agent":
            if agents and disallows:
                blocks.append((agents[:], disallows[:], allows[:]))
                agents, disallows, allows = [], [], []
            agents.append(value)
        elif field == "disallow":
            disallows.append(value)
        elif field == "allow":
            allows.append(value)

    if agents:
        blocks.append((agents, disallows, allows))
    return blocks


def _resolve_permission(disallows: list[str], _allows: list[str]) -> CrawlerPermission:
    """Determine CrawlerPermission from disallow list."""
    if any(d == "/" for d in disallows):
        return CrawlerPermission.disallowed
    if any(d.startswith("/") for d in disallows if d):
        return CrawlerPermission.partial
    return CrawlerPermission.allowed


def parse_robots_txt(content: str) -> dict[str, CrawlerPermission]:
    """Parse robots.txt and return permission for each AI crawler."""
    permissions: dict[str, CrawlerPermission] = {
        c: CrawlerPermission.allowed for c in AI_CRAWLERS
    }
    blocks = _parse_blocks(content)

    # Apply wildcard rules first
    for agents, disallows, allows in blocks:
        if "*" in agents:
            perm = _resolve_permission(disallows, allows)
            for crawler in AI_CRAWLERS:
                permissions[crawler] = perm
            break

    # Override with specific crawler rules
    for agents, disallows, allows in blocks:
        for agent in agents:
            if agent == "*":
                continue
            for crawler in AI_CRAWLERS:
                if crawler.lower() == agent.lower():
                    permissions[crawler] = _resolve_permission(disallows, allows)

    return permissions


async def analyze_robots_txt(domain: str, client: httpx.AsyncClient) -> RobotsAnalysis:
    """Orchestrates fetch + parse, returns full RobotsAnalysis."""
    raw_content = await fetch_robots_txt(domain, client)

    if raw_content is None:
        return RobotsAnalysis(
            raw_content=None,
            crawler_permissions={c: CrawlerPermission.allowed for c in AI_CRAWLERS},
            has_ai_crawler_rules=False,
        )

    try:
        permissions = parse_robots_txt(raw_content)
    except Exception as exc:
        logger.warning("robots.txt parse error", domain=domain, error=str(exc))
        permissions = {c: CrawlerPermission.partial for c in AI_CRAWLERS}

    has_ai_rules = any(c.lower() in raw_content.lower() for c in AI_CRAWLERS)

    return RobotsAnalysis(
        raw_content=raw_content,
        crawler_permissions=permissions,
        has_ai_crawler_rules=has_ai_rules,
    )
