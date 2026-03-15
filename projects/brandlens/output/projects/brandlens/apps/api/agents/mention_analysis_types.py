from dataclasses import dataclass
from typing import List, Optional

@dataclass
class MentionRecord:
    audit_id: str
    response_id: str
    entity_name: str
    mention_type: str             # see VALID_MENTION_TYPES
    position_rank: Optional[int]    # 1 = first mentioned entity; None if absent
    sentiment_score: float        # clamped [-1.0, 1.0]
    sentiment_label: str          # "positive" | "negative" | "neutral"
    authority_markers: List[str]  # filtered against KNOWN_AUTHORITY_MARKERS
    is_authority_cite: bool
    extracted_attributes: dict    # NER: category, key_products, founding_date, location, leadership
    is_confused: bool
    confusion_note: Optional[str]


@dataclass
class ResponseRow:
    id: str            # audit_responses.id (UUID)
    response_text: str
    platform: str      # ai_platform enum value string
    query_text: str    # joined from audit_queries table
    audit_id: str      # Added for convenience, from state.audit_id
