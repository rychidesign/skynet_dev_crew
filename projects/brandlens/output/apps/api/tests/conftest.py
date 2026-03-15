import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from apps.api.agents.competitor_mapper_constants_and_types import AuditStatus, FilteredResponse
from apps.api.agents.competitor_mapper_constants_and_types import CompetitorRecord # For type hinting
from apps.api.core.state import AuditState

# Mock structlog for tests
@pytest.fixture(autouse=True)
def mock_structlog():
    with patch("structlog.get_logger") as mock_get_logger:
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        yield mock_logger

# Fixtures for common data
@pytest.fixture
def mock_audit_state():
    state = AuditState(
        audit_id="test-audit-id",
        company_id="test-company-id",
        user_id="test-user-id",
        organization_id="test-org-id",
        status=AuditStatus.RUNNING,
        messages=[],
        audit_config={},
        company_name="TestCompany",
        company_website="testcompany.com",
        company_facts=[],
        company_competitors=["CompetitorA", "CompetitorB.com", "CompetitorC"],
        company_core_topics=[],
        query_results=[],
        response_results=[],
        mention_results=[],
        competitor_results=[],
        metric_scores={},
        recommendations=[],
        technical_checks={},
        audit_events=[],
        brand_competitive_stats=[],
    )
    state.get_db = AsyncMock()
    state.get_db.return_value = MagicMock()
    return state

@pytest.fixture
def mock_db_client():
    db = AsyncMock()
    db.from_.return_value.select.return_value.eq.return_value.in_.return_value.execute.return_value = AsyncMock(data=[])
    db.from_.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = AsyncMock(data={})
    db.from_.return_value.upsert.return_value.on_conflict.return_value.execute.return_value = AsyncMock(data=[])
    return db

@pytest.fixture
def mock_redis_client():
    redis = AsyncMock()
    return redis
