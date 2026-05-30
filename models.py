from pydantic import BaseModel, Field
from datetime import datetime, date, timezone
from typing import Optional
import uuid


LIFE_CATEGORIES = [
    "career",
    "financial",
    "health",
    "creative",
    "learning",
    "relationships",
    "lifestyle",
    "wellbeing",
]


def _id() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Memory(BaseModel):
    id: str = Field(default_factory=_id)
    user_id: str = "default"
    content: str
    type: str = "fact"  # "fact" | "note"
    tags: list[str] = []
    category: str = "general"
    mood: Optional[str] = None
    emotion_tags: list[str] = []
    importance: int = 5
    source: str = "unknown"
    created_at: datetime = Field(default_factory=_now)


class Goal(BaseModel):
    id: str = Field(default_factory=_id)
    user_id: str = "default"
    title: str
    category: str
    progress: int = 0
    milestones: list[dict] = []
    deadline: Optional[str] = None
    status: str = "active"
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class Event(BaseModel):
    id: str = Field(default_factory=_id)
    user_id: str = "default"
    title: str
    category: str
    event_date: str
    people_involved: list[str] = []
    outcome: Optional[str] = None
    follow_up_sent: bool = False
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)


class FinancialFact(BaseModel):
    id: str = Field(default_factory=_id)
    user_id: str = "default"
    type: str
    asset: str
    amount: float
    currency: str = "INR"
    transaction_date: str
    status: str = "active"
    notes: Optional[str] = None
    follow_up_sent: bool = False
    created_at: datetime = Field(default_factory=_now)


class Skill(BaseModel):
    id: str = Field(default_factory=_id)
    user_id: str = "default"
    name: str
    domain: str
    proficiency: str = "intermediate"
    actively_using: bool = True
    notes: Optional[str] = None
    updated_at: datetime = Field(default_factory=_now)


class Relationship(BaseModel):
    id: str = Field(default_factory=_id)
    user_id: str = "default"
    name: str
    relationship_type: str
    notes: Optional[str] = None
    last_mentioned: datetime = Field(default_factory=_now)
    created_at: datetime = Field(default_factory=_now)


class DelegatedTask(BaseModel):
    id: str = Field(default_factory=_id)
    user_id: str = "default"
    description: str
    category: str
    source: str = "unknown"
    status: str = "active"
    check_in_date: Optional[str] = None
    outcome: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class Followup(BaseModel):
    id: str = Field(default_factory=_id)
    user_id: str = "default"
    question: str
    source_entity_type: str
    source_entity_id: str
    status: str = "pending"
    answer: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)
    answered_at: Optional[datetime] = None
