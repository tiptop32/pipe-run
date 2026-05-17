import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.db.base import get_db_session
from app.features.pipelines.crud import (
    create_user_project,
    delete_user_project,
    get_user_project,
    list_user_projects,
)
from app.features.projects.schemas import UserProjectCreate, UserProjectOut

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


@router.get("", response_model=list[UserProjectOut])
async def list_projects(
    user_id: int = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    return await list_user_projects(session, user_id)


@router.post("", response_model=UserProjectOut, status_code=201)
async def create_project(
    body: UserProjectCreate,
    user_id: int = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    return await create_user_project(
        session,
        user_id=user_id,
        gitlab_project_id=body.gitlab_project_id,
        display_name=body.display_name,
        allure_results_path=body.allure_results_path,
    )


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: uuid.UUID,
    user_id: int = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    project = await get_user_project(session, project_id)
    if project is None or project.user_id != user_id:
        raise HTTPException(status_code=404, detail="Project not found")

    await delete_user_project(session, project_id)
