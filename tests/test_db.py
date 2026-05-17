from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine

from app.db.base import Base
from app.db import models  # noqa — registers all models


async def test_tables_created_via_create_all():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with engine.connect() as conn:
        tables = await conn.run_sync(lambda c: inspect(c).get_table_names())

    assert "user_projects" in tables
    assert "custom_pipelines" in tables
    assert "schedule_bookmarks" in tables
    assert "allure_reports" in tables
    await engine.dispose()


async def test_new_schema_columns():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with engine.connect() as conn:
        pipeline_cols = await conn.run_sync(
            lambda c: [col["name"] for col in inspect(c).get_columns("custom_pipelines")]
        )
        bookmark_cols = await conn.run_sync(
            lambda c: [col["name"] for col in inspect(c).get_columns("schedule_bookmarks")]
        )
        project_cols = await conn.run_sync(
            lambda c: [col["name"] for col in inspect(c).get_columns("user_projects")]
        )
        allure_cols = await conn.run_sync(
            lambda c: [col["name"] for col in inspect(c).get_columns("allure_reports")]
        )

    assert "user_id" in pipeline_cols
    assert "project_id" in pipeline_cols
    assert "user_id" in bookmark_cols
    assert "project_id" in bookmark_cols
    assert "gitlab_project_id" in project_cols
    assert "allure_results_path" in project_cols
    assert "status" in allure_cols
    assert "gitlab_project_id" in allure_cols
    await engine.dispose()
