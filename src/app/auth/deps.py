from fastapi import HTTPException, Request

from app.features.pipelines.gitlab import GitLabClient
from app.conf import config


def get_current_user(request: Request) -> int:
    user_id = getattr(request.state, "user_id", None)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user_id


def get_gitlab_token(request: Request) -> str:
    token = getattr(request.state, "gitlab_token", None)
    if token is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return token


def make_gitlab_client(gitlab_project_id: int, token: str) -> GitLabClient:
    return GitLabClient(
        base_url=config.GITLAB_BASE_URL,
        access_token=token,
        project_id=gitlab_project_id,
    )
