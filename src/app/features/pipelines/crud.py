import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.pipelines.models import AllureReport, CustomPipeline, ScheduleBookmark, UserProject


# --- UserProject ---

async def create_user_project(
    session: AsyncSession,
    user_id: int,
    gitlab_project_id: int,
    display_name: str,
    allure_results_path: str | None = None,
) -> UserProject:
    project = UserProject(
        user_id=user_id,
        gitlab_project_id=gitlab_project_id,
        display_name=display_name,
        allure_results_path=allure_results_path,
    )
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


async def list_user_projects(session: AsyncSession, user_id: int) -> list[UserProject]:
    result = await session.execute(
        select(UserProject).where(UserProject.user_id == user_id).order_by(UserProject.created_at)
    )
    return list(result.scalars().all())


async def get_user_project(session: AsyncSession, project_id: uuid.UUID) -> UserProject | None:
    result = await session.execute(select(UserProject).where(UserProject.id == project_id))
    return result.scalar_one_or_none()


async def get_user_project_by_gitlab_id(
    session: AsyncSession, user_id: int, gitlab_project_id: int
) -> UserProject | None:
    result = await session.execute(
        select(UserProject).where(
            UserProject.user_id == user_id,
            UserProject.gitlab_project_id == gitlab_project_id,
        )
    )
    return result.scalar_one_or_none()


async def delete_user_project(session: AsyncSession, project_id: uuid.UUID) -> bool:
    result = await session.execute(select(UserProject).where(UserProject.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        return False
    await session.delete(project)
    await session.commit()
    return True


# --- CustomPipeline ---

async def create_custom_pipeline(
    session: AsyncSession,
    user_id: int,
    project_id: uuid.UUID,
    name: str,
    ref: str,
    variables: list,
    seeded_from_schedule_id: int | None = None,
) -> CustomPipeline:
    cfg = CustomPipeline(
        user_id=user_id,
        project_id=project_id,
        name=name,
        ref=ref,
        variables=variables,
        seeded_from_schedule_id=seeded_from_schedule_id,
    )
    session.add(cfg)
    await session.commit()
    await session.refresh(cfg)
    return cfg


async def get_custom_pipeline(session: AsyncSession, config_id: uuid.UUID) -> CustomPipeline | None:
    result = await session.execute(select(CustomPipeline).where(CustomPipeline.id == config_id))
    return result.scalar_one_or_none()


async def list_custom_pipelines(
    session: AsyncSession, user_id: int, project_id: uuid.UUID
) -> list[CustomPipeline]:
    result = await session.execute(
        select(CustomPipeline)
        .where(CustomPipeline.user_id == user_id, CustomPipeline.project_id == project_id)
        .order_by(CustomPipeline.created_at)
    )
    return list(result.scalars().all())


async def update_custom_pipeline(
    session: AsyncSession,
    config_id: uuid.UUID,
    **fields,
) -> CustomPipeline | None:
    result = await session.execute(select(CustomPipeline).where(CustomPipeline.id == config_id))
    cfg = result.scalar_one_or_none()
    if cfg is None:
        return None
    for key, value in fields.items():
        setattr(cfg, key, value)
    await session.commit()
    await session.refresh(cfg)
    return cfg


async def delete_custom_pipeline(session: AsyncSession, config_id: uuid.UUID) -> bool:
    result = await session.execute(select(CustomPipeline).where(CustomPipeline.id == config_id))
    cfg = result.scalar_one_or_none()
    if cfg is None:
        return False
    await session.delete(cfg)
    await session.commit()
    return True


async def update_last_run(
    session: AsyncSession,
    cfg: CustomPipeline,
    pipeline_id: int,
    pipeline_status: str | None = None,
) -> None:
    cfg.last_pipeline_id = pipeline_id
    cfg.last_pipeline_status = pipeline_status
    cfg.last_run_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(cfg)


# --- ScheduleBookmark ---

async def add_schedule_bookmark(
    session: AsyncSession,
    user_id: int,
    project_id: uuid.UUID,
    schedule_id: int,
    display_name: str | None = None,
) -> ScheduleBookmark:
    bookmark = ScheduleBookmark(
        user_id=user_id,
        project_id=project_id,
        schedule_id=schedule_id,
        display_name=display_name,
    )
    session.add(bookmark)
    await session.commit()
    await session.refresh(bookmark)
    return bookmark


async def list_schedule_bookmarks(
    session: AsyncSession, user_id: int, project_id: uuid.UUID
) -> list[ScheduleBookmark]:
    result = await session.execute(
        select(ScheduleBookmark)
        .where(ScheduleBookmark.user_id == user_id, ScheduleBookmark.project_id == project_id)
        .order_by(ScheduleBookmark.created_at)
    )
    return list(result.scalars().all())


async def get_schedule_bookmark(session: AsyncSession, bookmark_id: uuid.UUID) -> ScheduleBookmark | None:
    result = await session.execute(select(ScheduleBookmark).where(ScheduleBookmark.id == bookmark_id))
    return result.scalar_one_or_none()


async def delete_schedule_bookmark(session: AsyncSession, bookmark_id: uuid.UUID) -> bool:
    result = await session.execute(select(ScheduleBookmark).where(ScheduleBookmark.id == bookmark_id))
    bookmark = result.scalar_one_or_none()
    if bookmark is None:
        return False
    await session.delete(bookmark)
    await session.commit()
    return True


# --- AllureReport ---

async def upsert_allure_report_status(
    session: AsyncSession,
    pipeline_id: int,
    gitlab_project_id: int,
    status: str,
    error_text: str | None = None,
) -> AllureReport:
    result = await session.execute(
        select(AllureReport).where(AllureReport.pipeline_id == pipeline_id)
    )
    report = result.scalar_one_or_none()
    if report is None:
        report = AllureReport(
            pipeline_id=pipeline_id,
            gitlab_project_id=gitlab_project_id,
            status=status,
            error_text=error_text,
        )
        session.add(report)
    else:
        report.status = status
        report.error_text = error_text
    await session.commit()
    await session.refresh(report)
    return report


async def get_allure_report_status(session: AsyncSession, pipeline_id: int) -> AllureReport | None:
    result = await session.execute(
        select(AllureReport).where(AllureReport.pipeline_id == pipeline_id)
    )
    return result.scalar_one_or_none()
