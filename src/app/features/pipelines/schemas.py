import uuid
from dataclasses import dataclass, field
from datetime import datetime

from pydantic import BaseModel, ConfigDict


@dataclass
class Variable:
    key: str
    value: str
    variable_type: str = "env_var"


@dataclass
class Schedule:
    id: int
    description: str
    ref: str
    active: bool = True
    variables: list[Variable] = field(default_factory=list)
    next_run_at: str | None = None


@dataclass
class Pipeline:
    id: int
    status: str
    ref: str
    web_url: str = ""
    created_at: str = ""


@dataclass
class Branch:
    name: str
    default: bool = False


@dataclass
class Job:
    id: int
    name: str
    status: str
    web_url: str = ""
    has_artifacts: bool = False


@dataclass
class StageInfo:
    name: str
    status: str
    jobs: list[Job] = field(default_factory=list)


@dataclass
class ScheduleDetail:
    id: int
    description: str
    ref: str
    active: bool = True
    next_run_at: str | None = None
    last_pipeline: Pipeline | None = None
    variables: list[Variable] = field(default_factory=list)


# ── Pydantic API schemas ───────────────────────────────────────────────────────


class PipelineConfigOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    ref: str
    variables: list[dict]
    last_pipeline_id: int | None
    last_pipeline_status: str | None
    last_run_at: datetime | None
    created_at: datetime


class PipelineConfigCreate(BaseModel):
    name: str
    ref: str = "main"
    variables: list[dict] = []
    seeded_from_schedule_id: int | None = None


class PipelineConfigUpdate(BaseModel):
    name: str
    ref: str
    variables: list[dict] = []


class ScheduleBookmarkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    schedule_id: int
    display_name: str | None
    created_at: datetime


class ScheduleBookmarkCreate(BaseModel):
    schedule_id: int
    display_name: str | None = None


class RunResult(BaseModel):
    config: PipelineConfigOut
    pipeline_id: int
    pipeline_status: str


class PipelineStatusUpdate(BaseModel):
    status: str
