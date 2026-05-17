import uuid

import httpx
import respx
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.conf import config
from app.db.base import get_db_session
from app.features.gitlab.router import bookmarks_router, router as gitlab_router
from app.features.pipelines.crud import create_user_project
from app.features.projects.router import router as projects_router

USER_ID = 42
GITLAB_PROJECT_ID = 100
BASE = config.GITLAB_BASE_URL.rstrip("/")


class FakeAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request.state.user_id = USER_ID
        request.state.gitlab_token = "glpat-fake"
        return await call_next(request)


def _make_app(session):
    app = FastAPI()
    app.add_middleware(FakeAuthMiddleware)
    app.include_router(gitlab_router)
    app.include_router(bookmarks_router)
    app.include_router(projects_router)
    app.dependency_overrides[get_db_session] = lambda: session
    return app


def _project_url(path: str) -> str:
    return f"{BASE}/api/v4/projects/{GITLAB_PROJECT_ID}/{path}"


@respx.mock
async def test_get_branches(async_session):
    respx.get(_project_url("repository/branches")).mock(
        return_value=httpx.Response(200, json=[{"name": "main"}, {"name": "dev"}])
    )
    app = _make_app(async_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/api/v1/gitlab/{GITLAB_PROJECT_ID}/branches")
        assert resp.status_code == 200
        assert "main" in resp.json()


@respx.mock
async def test_get_schedules(async_session):
    respx.get(_project_url("pipeline_schedules")).mock(
        return_value=httpx.Response(200, json=[
            {"id": 1, "description": "nightly", "ref": "main"},
            {"id": 2, "description": "smoke", "ref": "main"},
        ])
    )
    app = _make_app(async_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/api/v1/gitlab/{GITLAB_PROJECT_ID}/schedules?q=night")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == 1


@respx.mock
async def test_get_pipeline(async_session):
    respx.get(_project_url("pipelines/55")).mock(
        return_value=httpx.Response(200, json={"id": 55, "status": "success", "ref": "main", "web_url": ""})
    )
    app = _make_app(async_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/api/v1/gitlab/{GITLAB_PROJECT_ID}/pipelines/55")
        assert resp.status_code == 200
        assert resp.json()["id"] == 55


@respx.mock
async def test_run_schedule(async_session):
    respx.post(_project_url("pipeline_schedules/3/play")).mock(
        return_value=httpx.Response(201, json={"message": "201 Created"})
    )
    app = _make_app(async_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(f"/api/v1/gitlab/{GITLAB_PROJECT_ID}/schedules/3/run")
        assert resp.status_code == 200


async def test_allure_status_not_started(async_session):
    # IDOR fix: user must own the project — create it first
    await _create_project(async_session)
    app = _make_app(async_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/api/v1/gitlab/{GITLAB_PROJECT_ID}/pipelines/99/allure/status")
        assert resp.status_code == 200
        assert resp.json()["status"] == "not_started"


async def test_allure_status_404_without_project(async_session):
    app = _make_app(async_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/api/v1/gitlab/99999/pipelines/99/allure/status")
        assert resp.status_code == 404


# --- Bookmarks ---

async def _create_project(session) -> uuid.UUID:
    project = await create_user_project(
        session, user_id=USER_ID, gitlab_project_id=GITLAB_PROJECT_ID, display_name="Test"
    )
    return project.id


async def test_add_and_list_bookmarks(async_session):
    project_id = await _create_project(async_session)
    app = _make_app(async_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(f"/api/v1/projects/{project_id}/bookmarks", json={
            "schedule_id": 42, "display_name": "nightly"
        })
        assert resp.status_code == 201
        assert resp.json()["schedule_id"] == 42

        list_resp = await client.get(f"/api/v1/projects/{project_id}/bookmarks")
        assert list_resp.status_code == 200
        assert len(list_resp.json()) == 1


async def test_delete_bookmark(async_session):
    project_id = await _create_project(async_session)
    app = _make_app(async_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        add_resp = await client.post(f"/api/v1/projects/{project_id}/bookmarks", json={"schedule_id": 7})
        bookmark_id = add_resp.json()["id"]

        del_resp = await client.delete(f"/api/v1/projects/{project_id}/bookmarks/{bookmark_id}")
        assert del_resp.status_code == 204
