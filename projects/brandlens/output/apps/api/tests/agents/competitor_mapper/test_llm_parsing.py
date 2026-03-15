import pytest
from typing import List

from apps.api.agents.competitor_mapper_constants_and_types import CompetitorMentionResult
from apps.api.agents.competitor_mapper_llm_parsing import parse_llm_output

def test_parse_llm_output_valid_json(mock_structlog):
    raw_json = '''
    {
      "competitor_mentions": [
        {
          "competitor_name": "CompetitorA",
          "position_rank": 1,
          "is_recommended": true,
          "comparison_sentiment": "positive",
          "mention_count": 2
        },
        {
          "competitor_name": "CompetitorB",
          "position_rank": null,
          "is_recommended": false,
          "comparison_sentiment": "neutral",
          "mention_count": 1
        }
      ]
    }
    '''
    competitors = ["CompetitorA", "CompetitorB"]
    parsed = parse_llm_output(raw_json, "resp1", "audit1", competitors, mock_structlog)
    assert len(parsed) == 2
    assert parsed[0].competitor_name == "CompetitorA"
    assert parsed[0].position_rank == 1
    assert parsed[0].is_recommended is True
    assert parsed[0].comparison_sentiment == "positive"
    assert parsed[0].mention_count == 2

    assert parsed[1].competitor_name == "CompetitorB"
    assert parsed[1].position_rank is None
    assert parsed[1].is_recommended is False
    assert parsed[1].comparison_sentiment == "neutral"
    assert parsed[1].mention_count == 1
    mock_structlog.warning.assert_not_called()
    mock_structlog.error.assert_not_called()

def test_parse_llm_output_malformed_json(mock_structlog):
    raw_json = "{invalid json"
    competitors = ["CompetitorA"]
    parsed = parse_llm_output(raw_json, "resp1", "audit1", competitors, mock_structlog)
    assert len(parsed) == 0
    mock_structlog.error.assert_called_once()

def test_parse_llm_output_invalid_competitor(mock_structlog):
    raw_json = '''
    {
      "competitor_mentions": [
        {
          "competitor_name": "UnknownComp",
          "position_rank": 1,
          "is_recommended": true,
          "comparison_sentiment": "positive",
          "mention_count": 1
        }
      ]
    }
    '''
    competitors = ["CompetitorA"]
    parsed = parse_llm_output(raw_json, "resp1", "audit1", competitors, mock_structlog)
    assert len(parsed) == 0
    mock_structlog.warning.assert_called_once_with(
        "LLM returned invalid competitor name or one not in list",
        raw_name="UnknownComp",
        response_id="resp1",
        audit_id="audit1",
    )

def test_parse_llm_output_invalid_sentiment(mock_structlog):
    raw_json = '''
    {
      "competitor_mentions": [
        {
          "competitor_name": "CompetitorA",
          "position_rank": 1,
          "is_recommended": true,
          "comparison_sentiment": "unknown_sentiment",
          "mention_count": 1
        }
      ]
    }
    '''
    competitors = ["CompetitorA"]
    parsed = parse_llm_output(raw_json, "resp1", "audit1", competitors, mock_structlog)
    assert len(parsed) == 1
    assert parsed[0].comparison_sentiment == "neutral"
    mock_structlog.warning.assert_called_once_with(
        "LLM returned invalid comparison_sentiment",
        sentiment="unknown_sentiment",
        competitor_name="CompetitorA",
        response_id="resp1",
        audit_id="audit1",
    )
