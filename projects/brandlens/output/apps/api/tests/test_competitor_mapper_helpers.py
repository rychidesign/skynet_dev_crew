import pytest
import json

from projects.brandlens.output.apps.api.agents.competitor_mapper.constants import CompetitorRecord
from projects.brandlens.output.apps.api.agents.competitor_mapper_helpers import (
    build_competitor_prompt, parse_competitor_llm_output, aggregate_competitor_stats,
    competitor_record_to_db_dict
)

@pytest.fixture
def mock_competitors():
    return ["CompetitorA", "CompetitorB", "CompetitorC"]

def test_build_competitor_prompt(mock_competitors):
    response_text = "Test response text."
    prompt = build_competitor_prompt(response_text, mock_competitors)
    assert len(prompt) == 2
    assert prompt[0]["role"] == "system"
    assert "expert brand analyst" in prompt[0]["content"]
    assert prompt[1]["role"] == "user"
    assert response_text in prompt[1]["content"]
    assert "CompetitorA, CompetitorB, CompetitorC" in prompt[1]["content"]

def test_parse_competitor_llm_output(mock_competitors):
    raw_json_output = """
    {
      "competitors_found": [
        {"name": "CompetitorA", "position_rank": 1, "is_recommended_first": true, "sentiment": "positive", "domain": "compA.com"},
        {"name": "CompetitorB", "position_rank": 2, "is_recommended_first": false, "sentiment": "neutral", "domain": "compB.io"},
        {"name": "UnknownComp", "position_rank": 3, "is_recommended_first": false, "sentiment": "negative"}
      ]
    }
    """
    parsed_hits = parse_competitor_llm_output(raw_json_output, "resp1", "chatgpt", mock_competitors)
    assert len(parsed_hits) == 2
    assert parsed_hits[0]["competitor_name"] == "CompetitorA"
    assert parsed_hits[0]["position_rank"] == 1
    assert parsed_hits[0]["is_recommended_first"] is True
    assert parsed_hits[0]["sentiment"] == "positive"
    assert parsed_hits[0]["domain"] == "compA.com"
    assert parsed_hits[1]["competitor_name"] == "CompetitorB"
    assert parsed_hits[1]["platform"] == "chatgpt"

    # Test with invalid JSON
    invalid_json = "{""competitors_found": [}"
    parsed_hits_invalid = parse_competitor_llm_output(invalid_json, "resp1", "chatgpt", mock_competitors)
    assert len(parsed_hits_invalid) == 0

    # Test with empty competitors_found
    empty_found_json = "{\"competitors_found\": []}"
    parsed_hits_empty = parse_competitor_llm_output(empty_found_json, "resp1", "chatgpt", mock_competitors)
    assert len(parsed_hits_empty) == 0

def test_aggregate_competitor_stats(mock_competitors):
    hits = [
        {"competitor_name": "CompetitorA", "position_rank": 1, "is_recommended_first": True, "sentiment": "positive", "platform": "chatgpt", "domain": "compA.com"},
        {"competitor_name": "CompetitorA", "position_rank": 2, "is_recommended_first": False, "sentiment": "neutral", "platform": "perplexity", "domain": "compA.net"},
        {"competitor_name": "CompetitorB", "position_rank": 3, "is_recommended_first": False, "sentiment": "negative", "platform": "chatgpt", "domain": "compB.io"},
        {"competitor_name": "CompetitorA", "position_rank": 1, "is_recommended_first": True, "sentiment": "positive", "platform": "chatgpt", "domain": "compA.com"},
    ]
    records = aggregate_competitor_stats(hits, mock_competitors, "test-audit-id")
    assert len(records) == 3 # All competitors should be present

    comp_a_record = next(r for r in records if r.competitor_name == "CompetitorA")
    assert comp_a_record.total_appearances == 3
    assert comp_a_record.avg_mention_position == pytest.approx((1+2+1)/3)
    assert comp_a_record.recommendation_count == 2
    assert comp_a_record.positive_comparisons == 2
    assert comp_a_record.negative_comparisons == 0
    assert comp_a_record.neutral_comparisons == 1
    assert comp_a_record.competitor_domain in ["compA.com", "compA.net"]
    assert "chatgpt" in comp_a_record.platform_breakdown
    assert comp_a_record.platform_breakdown["chatgpt"]["appearances"] == 2
    assert comp_a_record.platform_breakdown["chatgpt"]["avg_position"] == pytest.approx((1+1)/2)
    assert comp_a_record.platform_breakdown["chatgpt"]["recommendation_count"] == 2

    comp_b_record = next(r for r in records if r.competitor_name == "CompetitorB")
    assert comp_b_record.total_appearances == 1
    assert comp_b_record.avg_mention_position == pytest.approx(3.0)
    assert comp_b_record.recommendation_count == 0
    assert comp_b_record.positive_comparisons == 0
    assert comp_b_record.negative_comparisons == 1
    assert comp_b_record.neutral_comparisons == 0
    assert comp_b_record.competitor_domain == "compB.io"

    comp_c_record = next(r for r in records if r.competitor_name == "CompetitorC")
    assert comp_c_record.total_appearances == 0

def test_competitor_record_to_db_dict():
    record = CompetitorRecord(
        audit_id="aid1",
        competitor_name="CompX",
        competitor_domain="compx.ai",
        avg_mention_position=1.5,
        recommendation_count=1,
        total_appearances=2,
        positive_comparisons=1,
        negative_comparisons=0,
        neutral_comparisons=1,
        platform_breakdown={
            "chatgpt": {"appearances": 1, "avg_position": 1.0, "recommendation_count": 1, "positive_comparisons": 1, "negative_comparisons": 0, "neutral_comparisons": 0}
        },
    )
    db_dict = competitor_record_to_db_dict(record)
    assert db_dict["audit_id"] == "aid1"
    assert db_dict["competitor_name"] == "CompX"
    assert db_dict["platform_breakdown"] == record.platform_breakdown
    assert isinstance(db_dict["platform_breakdown"], dict)
