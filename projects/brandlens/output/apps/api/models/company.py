from pydantic import BaseModel, Field, ConfigDict, UUID4
from datetime import datetime

class CompanyBase(BaseModel):
    name: str = Field(..., min_length=1)
    domain: str | None = None
    industry: str | None = None
    description: str | None = None
    facts: dict = Field(default_factory=dict)
    competitors: list[str] = Field(default_factory=list)
    core_topics: list[str] = Field(default_factory=list)

class CompanyCreate(CompanyBase):
    pass

class CompanyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    domain: str | None = None
    industry: str | None = None
    description: str | None = None
    facts: dict | None = None
    competitors: list[str] | None = None
    core_topics: list[str] | None = None

class CompanyResponse(CompanyBase):
    id: UUID4
    organization_id: UUID4
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
