import pytest
import uuid

from app.features.pipelines.crud import (
    add_schedule_bookmark,
    create_custom_pipeline,
    create_user_project,
    delete_custom_pipeline,
    delete_schedule_bookmark,
    delete_user_project,
    get_allure_report_status,
    get_custom_pipeline,
    get_schedule_bookmark,
    get_user_project,
    list_custom_pipelines,
    list_schedule_bookmarks,
    list_user_projects,
    update_custom_pipeline,
    update_last_run,
    upsert_allure_report_status,
)

USER_ID = 42
GITLAB_PROJECT_ID = 100


# --- UserProject ---

async def test_create_and_get_user_project(async_session):
    project = await create_user_project(
        async_session, user_id=USER_ID, gitlab_project_id=GITLAB_PROJECT_ID,
        display_name="My Project"
    )
    assert project.id is not None
    assert project.user_id == USER_ID
    assert project.display_name == "My Project"
    assert project.allure_results_path is None

    fetched = await get_user_project(async_session, project.id)
    assert fetched is not None
    assert fetched.gitlab_project_id == GITLAB_PROJECT_ID


async def test_list_user_projects(async_session):
    await create_user_project(async_session, user_id=USER_ID, gitlab_project_id=1, display_name="A")
    await create_user_project(async_session, user_id=USER_ID, gitlab_project_id=2, display_name="B")
    await create_user_project(async_session, user_id=999, gitlab_project_id=3, display_name="Other")

    items = await list_user_projects(async_session, user_id=USER_ID)
    assert len(items) == 2


async def test_delete_user_project(async_session):
    project = await create_user_project(
        async_session, user_id=USER_ID, gitlab_project_id=GITLAB_PROJECT_ID, display_name="Del"
    )
    deleted = await delete_user_project(async_session, project.id)
    assert deleted is True
    assert await get_user_project(async_session, project.id) is None


async def test_delete_user_project_not_found(async_session):
    deleted = await delete_user_project(async_session, uuid.uuid4())
    assert deleted is False


# --- Helpers ---

async def _make_project(session):
    return await create_user_project(
        session, user_id=USER_ID, gitlab_project_id=GITLAB_PROJECT_ID, display_name="Test"
    )


# --- CustomPipeline ---

async def test_create_and_get_pipeline(async_session):
    project = await _make_project(async_session)
    cfg = await create_custom_pipeline(
        async_session, user_id=USER_ID, project_id=project.id,
        name="smoke", ref="main", variables=[]
    )
    assert cfg.id is not None
    assert cfg.name == "smoke"
    assert cfg.user_id == USER_ID

    fetched = await get_custom_pipeline(async_session, cfg.id)
    assert fetched is not None
    assert fetched.name == "smoke"


async def test_list_pipelines(async_session):
    project = await _make_project(async_session)
    await create_custom_pipeline(async_session, user_id=USER_ID, project_id=project.id, name="a", ref="main", variables=[])
    await create_custom_pipeline(async_session, user_id=USER_ID, project_id=project.id, name="b", ref="dev", variables=[])

    items = await list_custom_pipelines(async_session, user_id=USER_ID, project_id=project.id)
    assert len(items) == 2


async def test_list_pipelines_isolation(async_session):
    project1 = await create_user_project(async_session, user_id=1, gitlab_project_id=1, display_name="P1")
    project2 = await create_user_project(async_session, user_id=2, gitlab_project_id=2, display_name="P2")

    await create_custom_pipeline(async_session, user_id=1, project_id=project1.id, name="a", ref="main", variables=[])
    await create_custom_pipeline(async_session, user_id=2, project_id=project2.id, name="b", ref="main", variables=[])

    items = await list_custom_pipelines(async_session, user_id=1, project_id=project1.id)
    assert len(items) == 1
    assert items[0].name == "a"


async def test_update_pipeline(async_session):
    project = await _make_project(async_session)
    cfg = await create_custom_pipeline(
        async_session, user_id=USER_ID, project_id=project.id, name="old", ref="main", variables=[]
    )
    updated = await update_custom_pipeline(async_session, cfg.id, name="new", ref="feature")
    assert updated is not None
    assert updated.name == "new"
    assert updated.ref == "feature"


async def test_update_pipeline_not_found(async_session):
    result = await update_custom_pipeline(async_session, uuid.uuid4(), name="x", ref="y")
    assert result is None


async def test_delete_pipeline(async_session):
    project = await _make_project(async_session)
    cfg = await create_custom_pipeline(
        async_session, user_id=USER_ID, project_id=project.id, name="del", ref="main", variables=[]
    )
    deleted = await delete_custom_pipeline(async_session, cfg.id)
    assert deleted is True
    assert await get_custom_pipeline(async_session, cfg.id) is None


async def test_delete_pipeline_not_found(async_session):
    deleted = await delete_custom_pipeline(async_session, uuid.uuid4())
    assert deleted is False


async def test_update_last_run(async_session):
    project = await _make_project(async_session)
    cfg = await create_custom_pipeline(
        async_session, user_id=USER_ID, project_id=project.id, name="run", ref="main", variables=[]
    )
    await update_last_run(async_session, cfg, pipeline_id=999, pipeline_status="running")
    assert cfg.last_pipeline_id == 999
    assert cfg.last_pipeline_status == "running"
    assert cfg.last_run_at is not None


# --- ScheduleBookmark ---

async def test_add_and_list_bookmarks(async_session):
    project = await _make_project(async_session)
    bm = await add_schedule_bookmark(
        async_session, user_id=USER_ID, project_id=project.id,
        schedule_id=42, display_name="nightly"
    )
    assert bm.id is not None
    assert bm.schedule_id == 42

    items = await list_schedule_bookmarks(async_session, user_id=USER_ID, project_id=project.id)
    assert len(items) == 1
    assert items[0].display_name == "nightly"


async def test_get_bookmark(async_session):
    project = await _make_project(async_session)
    bm = await add_schedule_bookmark(async_session, user_id=USER_ID, project_id=project.id, schedule_id=7)
    fetched = await get_schedule_bookmark(async_session, bm.id)
    assert fetched is not None
    assert fetched.schedule_id == 7


async def test_delete_bookmark(async_session):
    project = await _make_project(async_session)
    bm = await add_schedule_bookmark(async_session, user_id=USER_ID, project_id=project.id, schedule_id=5)
    deleted = await delete_schedule_bookmark(async_session, bm.id)
    assert deleted is True
    assert await get_schedule_bookmark(async_session, bm.id) is None


async def test_delete_bookmark_not_found(async_session):
    deleted = await delete_schedule_bookmark(async_session, uuid.uuid4())
    assert deleted is False


# --- AllureReport ---

async def test_upsert_allure_report(async_session):
    report = await upsert_allure_report_status(
        async_session, pipeline_id=10, gitlab_project_id=GITLAB_PROJECT_ID, status="pending"
    )
    assert report.pipeline_id == 10
    assert report.status == "pending"
    assert report.error_text is None


async def test_upsert_allure_report_updates(async_session):
    await upsert_allure_report_status(
        async_session, pipeline_id=20, gitlab_project_id=GITLAB_PROJECT_ID, status="pending"
    )
    updated = await upsert_allure_report_status(
        async_session, pipeline_id=20, gitlab_project_id=GITLAB_PROJECT_ID,
        status="error", error_text="allure CLI failed"
    )
    assert updated.status == "error"
    assert updated.error_text == "allure CLI failed"


async def test_get_allure_report_status_none(async_session):
    result = await get_allure_report_status(async_session, pipeline_id=9999)
    assert result is None
