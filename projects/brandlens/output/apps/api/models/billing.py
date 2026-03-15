from enum import Enum
from typing import Optional, Any
from pydantic import BaseModel


class OrgRole(str, Enum):
    owner = "owner"
    admin = "admin"
    analyst = "analyst"
    viewer = "viewer"


class SubscriptionPlan(BaseModel):
    id: str
    organization_id: str
    paddle_subscription_id: Optional[str] = None
    paddle_customer_id: Optional[str] = None
    status: str
    plan: str
    current_period_start: Optional[str] = None
    current_period_end: Optional[str] = None
    cancel_at: Optional[str] = None


class WebhookPayload(BaseModel):
    event_type: str
    data: dict[str, Any]
    occurred_at: str
    notification_id: str
