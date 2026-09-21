from datetime import date
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .database import today


class Input(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class ProfileInput(Input):
    name: str = Field(min_length=1, max_length=40)
    exam_name: str = Field(min_length=1, max_length=100)
    exam_date: date | None = None
    daily_goal_minutes: int = Field(ge=5, le=1440)


class SubjectInput(Input):
    name: str = Field(min_length=1, max_length=40)
    kind: Literal["practice", "essay"] = "practice"


class PlanInput(Input):
    title: str = Field(min_length=1, max_length=150)
    subject_id: str
    scheduled_date: date
    minutes: int = Field(ge=1, le=1440)
    note: str = Field(default="", max_length=2000)


class LogInput(Input):
    id: UUID = Field(default_factory=uuid4)
    title: str = Field(min_length=1, max_length=150)
    subject_id: str
    study_date: date
    duration_minutes: int = Field(ge=1, le=1440)
    question_count: int = Field(default=0, ge=0, le=5000)
    correct_count: int = Field(default=0, ge=0, le=5000)
    note: str = Field(default="", max_length=5000)
    plan_id: str | None = None
    add_to_review: bool = False

    @model_validator(mode="after")
    def validate_record(self):
        if self.study_date > today():
            raise ValueError("学习日期不能晚于今天")
        if self.correct_count > self.question_count:
            raise ValueError("正确题数不能超过总题数")
        return self


class ReviewInput(Input):
    title: str = Field(min_length=1, max_length=150)
    subject_id: str
    note: str = Field(default="", max_length=5000)
    source: str = Field(default="", max_length=500)
    due_date: date


class ReviewAction(Input):
    id: UUID = Field(default_factory=uuid4)
    rating: Literal["again", "hard", "good", "easy"]
    duration_minutes: int = Field(ge=1, le=240)
    expected_version: int = Field(ge=1)


class ArchiveInput(Input):
    archived: bool
