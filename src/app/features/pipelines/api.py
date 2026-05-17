import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user, get_gitlab_token, make_gitlab_client
from app.db.base import get_db_session
from app.features.pipelines.allure_report import generate_report, get_report_status, report_url
from app.features.pipelines.crud import (
    create_custom_pipeline,
    delete_custom_pipeline,
    get_custom_pipeline,
    get_user_project,
    list_custom_pipelines,
    update_custom_pipeline,
    update_last_run,
)
from app.features.pipelines.schemas import (
    PipelineConfigCreate,
    PipelineConfigOut,
    PipelineConfigUpdate,
    PipelineStatusUpdate,
    RunResult,
)
from app.features.pipelines.gitlab import GitLabAPIError

router = APIRouter(prefix="/api/v1/projects/{project_id}/configs", tags=["pipelines"])


async def _get_project_or_404(project_id: uuid.UUID, user_id: int, session: AsyncSession):
    project = await get_user_project(session, project_id)
    if project is None or project.user_id != user_id:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.get("", response_model=list[PipelineConfigOut])
async def list_configs(
    project_id: uuid.UUID,
    user_id: int = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    await _get_project_or_404(project_id, user_id, session)
    return await list_custom_pipelines(session, user_id=user_id, project_id=project_id)


@router.post("", response_model=PipelineConfigOut, status_code=201)
async def create_config(
    project_id: uuid.UUID,
    body: PipelineConfigCreate,
    user_id: int = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    await _get_project_or_404(project_id, user_id, session)
    return await create_custom_pipeline(
        session,
        user_id=user_id,
        project_id=project_id,
        name=body.name,
        ref=body.ref,
        variables=body.variables,
        seeded_from_schedule_id=body.seeded_from_schedule_id,
    )


@router.put("/{config_id}", response_model=PipelineConfigOut)
async def update_config(
    project_id: uuid.UUID,
    config_id: uuid.UUID,
    body: PipelineConfigUpdate,
    user_id: int = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    await _get_project_or_404(project_id, user_id, session)
    updated = await update_custom_pipeline(
        session, config_id, name=body.name, ref=body.ref, variables=body.variables
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Config not found")
    return updated


@router.delete("/{config_id}", status_code=204)
async def delete_config(
    project_id: uuid.UUID,
    config_id: uuid.UUID,
    user_id: int = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    await _get_project_or_404(project_id, user_id, session)
    deleted = await delete_custom_pipeline(session, config_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Config not found")


@router.post("/{config_id}/run", response_model=RunResult)
async def run_config(
    project_id: uuid.UUID,
    config_id: uuid.UUID,
    user_id: int = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    token: str = Depends(get_gitlab_token),
):
    project = await _get_project_or_404(project_id, user_id, session)
    cfg = await get_custom_pipeline(session, config_id)
    if cfg is None:
        raise HTTPException(status_code=404, detail="Config not found")

    gl = make_gitlab_client(project.gitlab_project_id, token=token)
    try:
        pipeline = await gl.run_pipeline(cfg.ref, cfg.variables)
    except GitLabAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)

    await update_last_run(session, cfg, pipeline_id=pipeline.id, pipeline_status=pipeline.status)
    return RunResult(
        config=PipelineConfigOut.model_validate(cfg),
        pipeline_id=pipeline.id,
        pipeline_status=pipeline.status,
    )


@router.patch("/{config_id}/pipeline-status", response_model=PipelineConfigOut)
async def update_pipeline_status(
    project_id: uuid.UUID,
    config_id: uuid.UUID,
    body: PipelineStatusUpdate,
    user_id: int = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    await _get_project_or_404(project_id, user_id, session)
    updated = await update_custom_pipeline(session, config_id, last_pipeline_status=body.status)
    if updated is None:
        raise HTTPException(status_code=404, detail="Config not found")
    return updated
