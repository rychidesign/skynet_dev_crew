import pytest
import statistics
from typing import List, Dict, Any, Tuple

from apps.api.agents.competitor_mapper_constants_and_types import CompetitorMentionResult, FilteredResponse, CompetitorRecord
from apps.api.agents.competitor_mapper_aggregation import aggregate_competitor_records, build_platform_breakdown, competitor_record_to_db_dict

def test_build_platform_breakdown():
    per_platform_data = {
        "ChatGPT": {
            "appearances": 2,
            "recommendation_count": 1,
            "position_ranks": [1, 3],
            "sentiments": ["positive", "neutral"],
        },
        "Gemini": {
            "appearances": 1,
            "recommendation_count": 0,
            "position_ranks": [2],
            "sentiments": ["negative"],
        },
    }
    breakdown = build_platform_breakdown(per_platform_data)
    assert "ChatGPT" in breakdown
    assert breakdown["ChatGPT"]["appearances"] == 2
    assert breakdown["ChatGPT"]["recommendation_count"] == 1
    assert breakdown["ChatGPT"]["avg_position"] == 2.0
    assert breakdown["ChatGPT"]["dominant_sentiment"] == "neutral" # Positive and neutral, so neutral is fine here.

    assert "Gemini" in breakdown
    assert breakdown["Gemini"]["appearances"] == 1
    assert breakdown["Gemini"]["recommendation_count"] == 0
    assert breakdown["Gemini"]["avg_position"] == 2.0
    assert breakdown["Gemini"]["dominant_sentiment"] == "negative"

def test_aggregate_competitor_records(mock_structlog):
    responses = [
        FilteredResponse("r1", "a1", "text1", "ChatGPT", "q1", "comparative"),
        FilteredResponse("r2", "a1", "text2", "Gemini", "q2", "recommendation"),
    ]
    mentions = [
        CompetitorMentionResult("CompA", 1, True, "positive", 1),
        CompetitorMentionResult("CompB", 2, False, "neutral", 1),
    ]
    mentions2 = [
        CompetitorMentionResult("CompA", 3, False, "negative", 1),
    ]

    all_mentions_across_responses = [
        (responses[0], mentions),
        (responses[1], mentions2),
    ]
    all_competitors = ["CompA", "CompB"]
    audit_id = "a1"

    records = aggregate_competitor_records(all_mentions_across_responses, all_competitors, audit_id, mock_structlog)

    assert len(records) == 2
    comp_a_record = next(r for r in records if r.competitor_name == "CompA")
    comp_b_record = next(r for r in records if r.competitor_name == "CompB")

    assert comp_a_record.audit_id == "a1"
    assert comp_a_record.competitor_name == "CompA"
    assert comp_a_record.avg_mention_position == 2.0 # (1+3)/2
    assert comp_a_record.recommendation_count == 1
    assert comp_a_record.total_appearances == 2
    assert comp_a_record.positive_comparisons == 1
    assert comp_a_record.negative_comparisons == 1
    assert comp_a_record.neutral_comparisons == 0
    assert "ChatGPT" in comp_a_record.platform_breakdown
    assert comp_a_record.platform_breakdown["ChatGPT"]["appearances"] == 1
    assert comp_a_record.platform_breakdown["Gemini"]["dominant_sentiment"] == "negative"

    assert comp_b_record.audit_id == "a1"
    assert comp_b_record.competitor_name == "CompB"
    assert comp_b_record.avg_mention_position == 2.0
    assert comp_b_record.recommendation_count == 0
    assert comp_b_record.total_appearances == 1
    assert comp_b_record.positive_comparisons == 0
    assert comp_b_record.negative_comparisons == 0
    assert comp_b_record.neutral_comparisons == 1
    assert "ChatGPT" in comp_b_record.platform_breakdown
    assert comp_b_record.platform_breakdown["ChatGPT"]["appearances"] == 1
    assert comp_b_record.platform_breakdown["ChatGPT"]["dominant_sentiment"] == "neutral"

def test_competitor_record_to_db_dict():
    record = CompetitorRecord(
        audit_id="a1",
        competitor_name="CompX",
        competitor_domain="compx.com",
        avg_mention_position=1.5,
        recommendation_count=1,
        total_appearances=2,
        positive_comparisons=1,
        negative_comparisons=0,
        neutral_comparisons=1,
        platform_breakdown={"ChatGPT": {"appearances": 2, "avg_position": 1.5}}
    )
    db_dict = competitor_record_to_db_dict(record)
    assert db_dict["audit_id"] == "a1"
    assert db_dict["competitor_name"] == "CompX"
    assert db_dict["competitor_domain"] == "compx.com"
    assert db_dict["avg_mention_position"] == 1.5
    assert db_dict["platform_breakdown"]["ChatGPT"]["appearances"] == 2
