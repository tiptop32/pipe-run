import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: int
    gitlab_project_id: int
    display_name: str
    allure_results_path: str | None
    created_at: datetime


class UserProjectCreate(BaseModel):
    gitlab_project_id: int
    display_name: str
    allure_results_path: str | None = None
