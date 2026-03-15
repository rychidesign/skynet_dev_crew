import json
from dataclasses import dataclass, field
from typing import List, Optional, Any
import structlog

# Initialize structlog logger
log = structlog.get_logger(__name__)

# Constants
KNOWN_AUTHORITY_MARKERS: List[str] = [
    "leading", "expert", "trusted", "top", "best",
    "pioneer", "industry leader", "renowned", "authoritative", "premier",
    "market leader", "innovator"
]

VALID_MENTION_TYPES: set[str] = {
    "primary", "secondary", "citation",
    "comparison", "recommendation", "absent"
}

SYSTEM_PROMPT: str = (
    "You are a brand mention extraction system. "
    "You analyze AI-generated responses and extract structured data about brand mentions. "
    "You MUST respond with valid JSON only. No explanation, no markdown, no prose. "
    "Follow the exact schema provided in the user message."
)

@dataclass
class MentionRecord:
    audit_id: str
    response_id: str
    entity_name: str
    mention_type: str           # "primary"|"secondary"|"citation"|"comparison"|"recommendation"|"absent"
    position_rank: Optional[int]    # 1 = first mentioned; None if absent
    sentiment_score: float      # clamped to [-1.0, 1.0]
    sentiment_label: str        # "positive"|"negative"|"neutral"
    authority_markers: List[str] # filtered against KNOWN_AUTHORITY_MARKERS
    is_authority_cite: bool
    extracted_attributes: dict  # NER: {category, key_products, founding_date, location, leadership}
    is_confused: bool
    confusion_note: Optional[str]

    def to_dict(self) -> dict:
        return {
            "audit_id": self.audit_id,
            "response_id": self.response_id,
            "entity_name": self.entity_name,
            "mention_type": self.mention_type,
            "position_rank": self.position_rank,
            "sentiment_score": self.sentiment_score,
            "sentiment_label": self.sentiment_label,
            "authority_markers": self.authority_markers,
            "is_authority_cite": self.is_authority_cite,
            "extracted_attributes": self.extracted_attributes,
            "is_confused": self.is_confused,
            "confusion_note": self.confusion_note,
        }


@dataclass
class ResponseRow:
    id: str          # audit_responses.id
    response_text: str
    platform: str    # ai_platform enum value
    query_text: str  # joined from audit_queries
    audit_id: str    # Added for convenience, from state.audit_id


def make_absent_mention(
    response_id: str,
    audit_id: str,
    company_name: str,
) -> MentionRecord:
    """Creates a fallback absent-mention record."""
    return MentionRecord(
        audit_id=audit_id,
        response_id=response_id,
        entity_name=company_name,
        mention_type="absent",
        position_rank=None,
        sentiment_score=0.0,
        sentiment_label="neutral",
        authority_markers=[],
        is_authority_cite=False,
        extracted_attributes={},
        is_confused=False,
        confusion_note=None,
    )

def build_analysis_prompt(
    response_text: str,
    company_name: str,
    platform: str,
    query_text: str,
) -> str:
    """Constructs the LLM prompt for mention extraction."""
    prompt = f'''
Analyze this AI response for mentions of the brand "{company_name}".

Platform: {platform}
Original query: {query_text}

Response to analyze:
---
{response_text}
---

Extract ALL mentions of "{company_name}" and return a JSON object with this exact schema:
{{
  "mentions": [
    {{
      "entity_name": "string",
      "mention_type": "primary|secondary|citation|comparison|recommendation|absent",
      "position_rank": "integer or null",
      "sentiment_score": "float from -1.0 to 1.0",
      "authority_markers": "[<strings from: {', '.join(KNOWN_AUTHORITY_MARKERS)}>]",
      "is_authority_cite": "boolean",
      "extracted_attributes": {{
        "category": "string or null",
        "key_products": "[<strings>]",
        "founding_date": "string or null",
        "location": "string or null",
        "leadership": "string or null"
      }},
      "is_confused": "boolean",
      "confusion_note": "string or null"
    }}
  ]
}}

Rules:
- If "{company_name}" is not mentioned at all, return one entry with mention_type "absent"
- position_rank is the ordinal rank of "{company_name}" among ALL named entities in the response
- authority_markers must only contain strings from the provided list
- is_confused is true only if the response clearly mixes up "{company_name}" with a different brand
'''
    return prompt.strip()


def parse_llm_output(
    raw_text: str,
    response_id: str,
    audit_id: str,
    company_name: str,
    log: structlog.BoundLogger,
) -> List[MentionRecord]:
    """
    Parses the LLM JSON response into MentionRecord list.
    Validates fields, applies defaults, guarantees >= 1 record.
    Falls back to absent mention on parse error.
    """
    mentions: List[MentionRecord] = []
    
    try:
        data = json.loads(raw_text)
        raw_mentions = data.get("mentions", [])

        if not isinstance(raw_mentions, list):
            raise ValueError("LLM output 'mentions' field must be a list.")

        for item in raw_mentions:
            if not isinstance(item, dict):
                log.warning("Invalid mention item format in LLM output, skipping.", item_type=type(item), item=item)
                continue

            mention_type = item.get("mention_type", "secondary")
            if mention_type not in VALID_MENTION_TYPES:
                log.warning("Invalid mention_type from LLM, defaulting to 'secondary'.", original_type=mention_type)
                mention_type = "secondary"

            position_rank = item.get("position_rank")
            if not (isinstance(position_rank, int) and position_rank >= 1) and position_rank is not None:
                log.warning("Invalid position_rank from LLM, defaulting to None.", original_rank=position_rank)
                position_rank = None
            
            sentiment_score = float(item.get("sentiment_score", 0.0))
            if not (-1.0 <= sentiment_score <= 1.0):
                log.warning("Sentiment score from LLM out of range, clamping.", original_score=sentiment_score)
                sentiment_score = max(-1.0, min(1.0, sentiment_score))
            
            # Derive sentiment_label from score, as per spec
            if sentiment_score > 0.1:
                sentiment_label = "positive"
            elif sentiment_score < -0.1:
                sentiment_label = "negative"
            else:
                sentiment_label = "neutral"

            authority_markers = [
                m for m in item.get("authority_markers", []) 
                if isinstance(m, str) and m.lower() in [marker.lower() for marker in KNOWN_AUTHORITY_MARKERS] # Case-insensitive check
            ]

            is_authority_cite = bool(item.get("is_authority_cite", False))
            is_confused = bool(item.get("is_confused", False))

            extracted_attributes = item.get("extracted_attributes", {})
            if not isinstance(extracted_attributes, dict):
                log.warning("Invalid extracted_attributes format, defaulting to empty dict.", original_attrs=extracted_attributes)
                extracted_attributes = {}
            else:
                if 'key_products' in extracted_attributes and not (isinstance(extracted_attributes['key_products'], list) and all(isinstance(p, str) for p in extracted_attributes['key_products'])):
                    log.warning("Invalid key_products format in extracted_attributes, defaulting to empty list.", original_key_products=extracted_attributes['key_products'])
                    extracted_attributes['key_products'] = []
                # Ensure other attributes are string or null, as LLM might generate other types
                for key in ['category', 'founding_date', 'location', 'leadership']:
                    if key in extracted_attributes and not (isinstance(extracted_attributes[key], str) or extracted_attributes[key] is None):
                        log.warning(f"Invalid type for extracted_attribute '{key}', converting to string or null.", original_value=extracted_attributes[key])
                        extracted_attributes[key] = str(extracted_attributes[key]) if extracted_attributes[key] is not None else None

            # Apply specific rules for "absent" mention type
            if mention_type == "absent":
                position_rank = None
                authority_markers = []
                is_authority_cite = False
                is_confused = False
                extracted_attributes = {} # Clear attributes if absent

            mentions.append(
                MentionRecord(
                    audit_id=audit_id,
                    response_id=response_id,
                    entity_name=item.get("entity_name", company_name), # Default to company_name if LLM fails to provide
                    mention_type=mention_type,
                    position_rank=position_rank,
                    sentiment_score=sentiment_score,
                    sentiment_label=sentiment_label,
                    authority_markers=authority_markers,
                    is_authority_cite=is_authority_cite,
                    extracted_attributes=extracted_attributes,
                    is_confused=is_confused,
                    confusion_note=item.get("confusion_note"),
                )
            )
        
        # Guarantee >= 1 record: If no valid mentions were parsed, create an absent one.
        if not mentions:
            log.warning("LLM output yielded no valid mentions after parsing, creating a fallback absent mention.", response_id=response_id)
            mentions.append(make_absent_mention(response_id, audit_id, company_name))

    except json.JSONDecodeError as e:
        log.error("Failed to decode LLM JSON response.", error=str(e), raw_json=raw_text, response_id=response_id)
        mentions = [make_absent_mention(response_id, audit_id, company_name)]
    except ValueError as e:
        log.error("Failed to parse LLM output due to value error.", error=str(e), raw_json=raw_text, response_id=response_id)
        mentions = [make_absent_mention(response_id, audit_id, company_name)]
    except Exception as e:
        log.error("An unexpected error occurred during LLM output parsing.", error=str(e), raw_json=raw_text, response_id=response_id)
        mentions = [make_absent_mention(response_id, audit_id, company_name)]

    return mentions
