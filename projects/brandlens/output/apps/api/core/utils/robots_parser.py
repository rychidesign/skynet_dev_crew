"""Fetch and parse robots.txt — returns per-crawler AI bot permissions for GEO-17."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import httpx
import structlog

log = structlog.get_logger(__name__)

TRACKED_CRAWLERS: list[str] = ["GPTBot", "ClaudeBot", "PerplexityBot", "Bingbot", "Googlebot"]
ROBOTS_FETCH_TIMEOUT: float = 10.0  # seconds

_SITEMAP_DIRECTIVE_RE = re.compile(r"^Sitemap:\s*(\S+)", re.IGNORECASE | re.MULTILINE)


@dataclass
class RobotsParseResult:
    raw_text: str | None                # full robots.txt text; None if unreachable
    crawler_permissions: dict[str, str] # {"GPTBot": "allowed", "ClaudeBot": "disallowed", ...}
    crawl_permission_score: float       # fraction of TRACKED_CRAWLERS that are allowed (0.0–1.0)
    sitemap_url_hint: str | None        # first Sitemap: directive URL; None if not found
    fetch_error: str | None             # error description on failure; None on success


# ---------------------------------------------------------------------------
# Parsing internals
# ---------------------------------------------------------------------------

def _parse_agent_blocks(text: str) -> dict[str, list[str]]:
    """
    Parse robots.txt into: user-agent-lower → list[disallow_path].
    Handles multi-agent stanzas and wildcard '*'.
    """
    disallowed: dict[str, list[str]] = {}
    current_agents: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()

        if not line:
            current_agents = []
            continue

        if line.startswith("#"):
            continue

        lower = line.lower()
        if lower.startswith("user-agent:"):
            agent = line.split(":", 1)[1].strip().lower()
            current_agents.append(agent)
            disallowed.setdefault(agent, [])
        elif lower.startswith("disallow:"):
            path = line.split(":", 1)[1].strip()
            for agent in current_agents:
                disallowed.setdefault(agent, []).append(path)

    return disallowed


def _paths_disallow_root(paths: list[str]) -> bool:
    """Return True if any disallow path blocks the root (i.e. '/')."""
    return any(p == "/" for p in paths)


def _bot_is_disallowed(bot_lower: str, blocks: dict[str, list[str]]) -> bool:
    """
    Determine if bot is disallowed. Exact block takes precedence over wildcard.
    If neither block exists, bot is allowed.
    """
    if bot_lower in blocks:
        return _paths_disallow_root(blocks[bot_lower])
    if "*" in blocks:
        return _paths_disallow_root(blocks["*"])
    return False


def _extract_sitemap_hint(text: str) -> str | None:
    """Return the first Sitemap: directive URL, or None if absent."""
    match = _SITEMAP_DIRECTIVE_RE.search(text)
    if match:
        url = match.group(1).strip()
        return url if url.startswith("http") else None
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def parse_robots(domain: str, client: httpx.AsyncClient) -> RobotsParseResult:
    """
    Fetch https://{domain}/robots.txt and compute per-crawler AI bot permissions.

    On fetch failure (404, timeout, connection error): raw_text=None, all bots default
    to "allowed" with crawl_permission_score=1.0 — robots.txt absence ≠ disallow.
    """
    url = f"https://{domain}/robots.txt"
    raw_text: str | None = None
    fetch_error: str | None = None

    try:
        response = await client.get(url, timeout=ROBOTS_FETCH_TIMEOUT)
        if response.status_code == 200:
            raw_text = response.text
        else:
            fetch_error = f"HTTP {response.status_code}"
    except httpx.TimeoutException as exc:
        fetch_error = f"Timeout: {exc}"
        log.warning("robots_fetch_timeout", domain=domain, error=str(exc))
    except httpx.ConnectError as exc:
        fetch_error = f"Connection error: {exc}"
        log.warning("robots_fetch_connect_error", domain=domain, error=str(exc))
    except httpx.RequestError as exc:
        fetch_error = f"Request error: {exc}"
        log.warning("robots_fetch_error", domain=domain, error=str(exc))

    if raw_text is None:
        permissions = {bot: "allowed" for bot in TRACKED_CRAWLERS}
        return RobotsParseResult(
            raw_text=None,
            crawler_permissions=permissions,
            crawl_permission_score=1.0,
            sitemap_url_hint=None,
            fetch_error=fetch_error,
        )

    blocks = _parse_agent_blocks(raw_text)
    permissions: dict[str, str] = {}
    allowed_count = 0

    for bot in TRACKED_CRAWLERS:
        is_dis = _bot_is_disallowed(bot.lower(), blocks)
        permissions[bot] = "disallowed" if is_dis else "allowed"
        if not is_dis:
            allowed_count += 1

    score = round(allowed_count / len(TRACKED_CRAWLERS), 4) if TRACKED_CRAWLERS else 0.0

    return RobotsParseResult(
        raw_text=raw_text,
        crawler_permissions=permissions,
        crawl_permission_score=score,
        sitemap_url_hint=_extract_sitemap_hint(raw_text),
        fetch_error=None,
    )
