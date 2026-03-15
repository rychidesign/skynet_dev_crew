"""Helper functions for Mention Analyzer agent."""
import json
from dataclasses import dataclass
from typing import List, Optional
import structlog

log = structlog.get_logger(__name__)

AGENT_NAME = "mention_analyzer"
ANALYSIS_SEMAPHORE_SIZE = 10
VALID_MENTION_TYPES = frozenset({"primary", "secondary", "citation", "comparison", "recommendation", "absent"})
KNOWN_AUTHORITY_MARKERS = ["leading", "expert", "trusted", "top", "best", "pioneer", "industry leader", "renowned", "authoritative", "premier", "market leader", "innovator"]
SENTIMENT_POSITIVE_THRESHOLD = 0.1
SENTIMENT_NEGATIVE_THRESHOLD = -0.1
LLM_TIMEOUT_SECONDS = 30.0
LLM_TEMPERATURE = 0.1

SYSTEM_PROMPT = """You are a brand mention extraction system. You analyze AI-generated responses and extract structured data about brand mentions. You MUST respond with valid JSON only. No explanation, no markdown, no prose. Follow the exact schema provided in the user message."""

@dataclass
class MentionRecord:
    audit_id: str
    response_id: str
    entity_name: str
    mention_type: str
    position_rank: Optional[int]
    sentiment_score: float
    sentiment_label: str
    authority_markers: List[str]
    is_authority_cite: bool
    extracted_attributes: dict
    is_confused: bool
    confusion_note: Optional[str]

@dataclass
class ResponseRow:
    id: str
    response_text: str
    platform: str
    query_text: str
    audit_id: str

def make_absent_mention(response_id: str, audit_id: str, company_name: str) -> MentionRecord:
    """Creates a single MentionRecord with mention_type='absent'."""
    return MentionRecord(audit_id=audit_id, response_id=response_id, entity_name=company_name, mention_type="absent",
        position_rank=None, sentiment_score=0.0, sentiment_label="neutral", authority_markers=[], is_authority_cite=False,
        extracted_attributes={}, is_confused=False, confusion_note=None)

def build_analysis_prompt(response_text: str, company_name: str, platform: str, query_text: str) -> str:
    """Builds the user-facing portion of the LLM prompt."""
    return f'''Analyze the following AI-generated response for mentions of the brand "{company_name}".

Context:
- Platform: {platform}
- Original query: {query_text}

Response to analyze:
---
{response_text}
---

Return a JSON object with this exact schema:
{{
  "mentions": [
    {{
      "entity_name": "string",
      "mention_type": "primary|secondary|citation|comparison|recommendation|absent",
      "position_rank": "integer or null",
      "sentiment_score": "float from -1.0 to 1.0",
      "authority_markers": "[<zero or more from: {', '.join(KNOWN_AUTHORITY_MARKERS)}>]",
      "is_authority_cite": "boolean",
      "extracted_attributes": {{"category": "string or null", "key_products": "[<product/service names>]", "founding_date": "YYYY or null", "location": "string or null", "leadership": "string or null"}},
      "is_confused": "boolean",
      "confusion_note": "brief explanation string or null"
    }}
  ]
}}

Rules:
- Return one entry per distinct mention of "{company_name}". Usually just one.
- If "{company_name}" does not appear in the response, return exactly one entry with mention_type "absent".
- position_rank counts ordinal position among ALL named entities (1 = first entity mentioned).
- Only include authority_markers that appear verbatim or semantically in the response.
- Set is_confused=true only when the response demonstrably mixes up "{company_name}" with a different brand.
'''.strip()

def derive_sentiment_label(score: float) -> str:
    """Derives sentiment_label from score."""
    if score > SENTIMENT_POSITIVE_THRESHOLD: return "positive"
    elif score < SENTIMENT_NEGATIVE_THRESHOLD: return "negative"
    return "neutral"

def clamp_sentiment(score: float) -> float:
    """Clamps score to [-1.0, 1.0]."""
    return max(-1.0, min(1.0, score))

def filter_authority_markers(raw_markers: List[str]) -> List[str]:
    """Returns only markers present in KNOWN_AUTHORITY_MARKERS (case-insensitive)."""
    known_lower = {m.lower() for m in KNOWN_AUTHORITY_MARKERS}
    return [m for m in raw_markers if isinstance(m, str) and m.lower() in known_lower]

def mention_record_to_db_dict(record: MentionRecord) -> dict:
    """Converts MentionRecord to a flat dict matching audit_mentions table columns."""
    return {"audit_id": record.audit_id, "response_id": record.response_id, "entity_name": record.entity_name,
        "mention_type": record.mention_type, "position_rank": record.position_rank, "sentiment_score": record.sentiment_score,
        "sentiment_label": record.sentiment_label, "authority_markers": record.authority_markers, "is_authority_cite": record.is_authority_cite,
        "extracted_attributes": record.extracted_attributes, "is_confused": record.is_confused, "confusion_note": record.confusion_note}

def parse_llm_output(raw_text: str, response_id: str, audit_id: str, company_name: str, log_ctx: structlog.BoundLogger) -> List[MentionRecord]:
    """Parses LLM JSON response string into validated MentionRecord list. Guarantees >= 1 record."""
    mentions: List[MentionRecord] = []
    try:
        data = json.loads(raw_text)
        raw_mentions = data.get("mentions", [])
        if not isinstance(raw_mentions, list):
            raise ValueError("LLM output 'mentions' field must be a list.")
        for item in raw_mentions:
            if not isinstance(item, dict):
                log_ctx.warning("Invalid mention item format, skipping", item_type=type(item))
                continue
            mention_type = item.get("mention_type", "secondary")
            if mention_type not in VALID_MENTION_TYPES:
                log_ctx.warning("Invalid mention_type, defaulting to 'secondary'", original_type=mention_type)
                mention_type = "secondary"
            position_rank = item.get("position_rank")
            if not (isinstance(position_rank, int) and position_rank >= 1) and position_rank is not None:
                log_ctx.warning("Invalid position_rank, defaulting to None", original_rank=position_rank)
                position_rank = None
            sentiment_score = clamp_sentiment(float(item.get("sentiment_score", 0.0)))
            sentiment_label = derive_sentiment_label(sentiment_score)
            authority_markers = filter_authority_markers(item.get("authority_markers", []))
            is_authority_cite = bool(item.get("is_authority_cite", False))
            is_confused = bool(item.get("is_confused", False))
            extracted_attributes = item.get("extracted_attributes", {})
            if not isinstance(extracted_attributes, dict):
                log_ctx.warning("Invalid extracted_attributes format, defaulting to empty dict")
                extracted_attributes = {}
            if mention_type == "absent":
                position_rank, authority_markers, is_authority_cite, is_confused, extracted_attributes = None, [], False, False, {}
            mentions.append(MentionRecord(audit_id=audit_id, response_id=response_id, entity_name=item.get("entity_name", company_name),
                mention_type=mention_type, position_rank=position_rank, sentiment_score=sentiment_score, sentiment_label=sentiment_label,
                authority_markers=authority_markers, is_authority_cite=is_authority_cite, extracted_attributes=extracted_attributes,
                is_confused=is_confused, confusion_note=item.get("confusion_note")))
        if not mentions:
            log_ctx.warning("LLM output yielded no valid mentions, creating fallback absent mention")
            mentions.append(make_absent_mention(response_id, audit_id, company_name))
    except json.JSONDecodeError as e:
        log_ctx.error("Failed to decode LLM JSON response", error=str(e))
        mentions = [make_absent_mention(response_id, audit_id, company_name)]
    except (KeyError, ValueError, TypeError) as e:
        log_ctx.error("Failed to parse LLM output", error=str(e))
        mentions = [make_absent_mention(response_id, audit_id, company_name)]
    return mentions
