import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user, get_gitlab_token, make_gitlab_client
from app.db.base import get_db_session
from app.features.pipelines.allure_report import generate_report, get_report_status, report_url
from app.features.pipelines.crud import (
    add_schedule_bookmark,
    delete_schedule_bookmark,
    get_schedule_bookmark,
    get_user_project,
    get_user_project_by_gitlab_id,
    list_schedule_bookmarks,
)
from app.features.pipelines.gitlab import GitLabAPIError
from app.features.pipelines.schemas import ScheduleBookmarkCreate, ScheduleBookmarkOut

router = APIRouter(prefix="/api/v1/gitlab/{gitlab_project_id}", tags=["gitlab"])
bookmarks_router = APIRouter(prefix="/api/v1/projects/{project_id}/bookmarks", tags=["bookmarks"])


@router.get("/branches")
async def get_branches(
    gitlab_project_id: int,
    token: str = Depends(get_gitlab_token),
):
    gl = make_gitlab_client(gitlab_project_id, token)
    try:
        return await gl.get_branches()
    except GitLabAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)


@router.get("/schedules")
async def get_schedules(
    gitlab_project_id: int,
    q: Annotated[str | None, Query()] = None,
    token: str = Depends(get_gitlab_token),
):
    gl = make_gitlab_client(gitlab_project_id, token)
    try:
        if q:
            return await gl.search_schedules(q)
        return await gl.get_pipeline_schedules()
    except GitLabAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)


@router.get("/schedules/{schedule_id}")
async def get_schedule(
    gitlab_project_id: int,
    schedule_id: int,
    token: str = Depends(get_gitlab_token),
):
    gl = make_gitlab_client(gitlab_project_id, token)
    try:
        return await gl.get_schedule(schedule_id)
    except GitLabAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)


@router.post("/schedules/{schedule_id}/run")
async def run_schedule(
    gitlab_project_id: int,
    schedule_id: int,
    token: str = Depends(get_gitlab_token),
):
    gl = make_gitlab_client(gitlab_project_id, token)
    try:
        return await gl.run_pipeline_schedule(schedule_id)
    except GitLabAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)


@router.get("/pipelines/{pipeline_id}")
async def get_pipeline(
    gitlab_project_id: int,
    pipeline_id: int,
    token: str = Depends(get_gitlab_token),
):
    gl = make_gitlab_client(gitlab_project_id, token)
    try:
        return await gl.get_pipeline(pipeline_id)
    except GitLabAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)


@router.post("/pipelines/{pipeline_id}/allure")
async def trigger_allure_report(
    gitlab_project_id: int,
    pipeline_id: int,
    job_id: int,
    background_tasks: BackgroundTasks,
    user_id: int = Depends(get_current_user),
    token: str = Depends(get_gitlab_token),
    session: AsyncSession = Depends(get_db_session),
):
    project = await get_user_project_by_gitlab_id(session, user_id, gitlab_project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.allure_results_path:
        raise HTTPException(status_code=400, detail="allure_results_path not configured for this project")

    gl = make_gitlab_client(gitlab_project_id, token)
    # generate_report opens its own DB session — the request session closes before the BG task runs
    background_tasks.add_task(
        generate_report, gl, pipeline_id, job_id, gitlab_project_id, project.allure_results_path
    )
    return {"status": "pending"}


@router.get("/pipelines/{pipeline_id}/allure/status")
async def allure_report_status(
    gitlab_project_id: int,
    pipeline_id: int,
    user_id: int = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    project = await get_user_project_by_gitlab_id(session, user_id, gitlab_project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    status = await get_report_status(session, pipeline_id)
    result = {"status": status}
    if status == "ready":
        result["url"] = report_url(pipeline_id)
    return result


# --- Schedule Bookmarks ---

@bookmarks_router.get("", response_model=list[ScheduleBookmarkOut])
async def list_bookmarks(
    project_id: uuid.UUID,
    user_id: int = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    project = await get_user_project(session, project_id)
    if project is None or project.user_id != user_id:
        raise HTTPException(status_code=404, detail="Project not found")
    return await list_schedule_bookmarks(session, user_id=user_id, project_id=project_id)


@bookmarks_router.post("", response_model=ScheduleBookmarkOut, status_code=201)
async def add_bookmark(
    project_id: uuid.UUID,
    body: ScheduleBookmarkCreate,
    user_id: int = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    project = await get_user_project(session, project_id)
    if project is None or project.user_id != user_id:
        raise HTTPException(status_code=404, detail="Project not found")
    return await add_schedule_bookmark(
        session, user_id=user_id, project_id=project_id,
        schedule_id=body.schedule_id, display_name=body.display_name,
    )


@bookmarks_router.delete("/{bookmark_id}", status_code=204)
async def remove_bookmark(
    project_id: uuid.UUID,
    bookmark_id: uuid.UUID,
    user_id: int = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    bookmark = await get_schedule_bookmark(session, bookmark_id)
    if bookmark is None or bookmark.user_id != user_id:
        raise HTTPException(status_code=404, detail="Bookmark not found")
    await delete_schedule_bookmark(session, bookmark_id)
