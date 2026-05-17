import uuid

import httpx
import respx
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.db.base import get_db_session
from app.features.pipelines.api import router as pipelines_router
from app.features.pipelines.crud import create_user_project
from app.features.projects.router import router as projects_router

USER_ID = 42
GITLAB_PROJECT_ID = 100
BASE = "https://gitlab.example.com"


class FakeAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request.state.user_id = USER_ID
        request.state.gitlab_token = "glpat-fake"
        return await call_next(request)


def _make_app(session):
    app = FastAPI()
    app.add_middleware(FakeAuthMiddleware)
    app.include_router(pipelines_router)
    app.include_router(projects_router)
    app.dependency_overrides[get_db_session] = lambda: session
    return app


async def _create_project(session) -> uuid.UUID:
    project = await create_user_project(
        session, user_id=USER_ID, gitlab_project_id=GITLAB_PROJECT_ID, display_name="Test"
    )
    return project.id


async def test_create_and_list_configs(async_session):
    project_id = await _create_project(async_session)
    app = _make_app(async_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(f"/api/v1/projects/{project_id}/configs", json={
            "name": "smoke",
            "ref": "main",
            "variables": [],
        })
        assert resp.status_code == 201
        assert resp.json()["name"] == "smoke"

        list_resp = await client.get(f"/api/v1/projects/{project_id}/configs")
        assert list_resp.status_code == 200
        assert len(list_resp.json()) == 1


async def test_update_config(async_session):
    project_id = await _create_project(async_session)
    app = _make_app(async_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_resp = await client.post(f"/api/v1/projects/{project_id}/configs", json={
            "name": "old", "ref": "main", "variables": [],
        })
        config_id = create_resp.json()["id"]

        upd_resp = await client.put(f"/api/v1/projects/{project_id}/configs/{config_id}", json={
            "name": "new", "ref": "feature",
        })
        assert upd_resp.status_code == 200
        assert upd_resp.json()["name"] == "new"


async def test_delete_config(async_session):
    project_id = await _create_project(async_session)
    app = _make_app(async_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_resp = await client.post(f"/api/v1/projects/{project_id}/configs", json={
            "name": "del", "ref": "main", "variables": [],
        })
        config_id = create_resp.json()["id"]

        del_resp = await client.delete(f"/api/v1/projects/{project_id}/configs/{config_id}")
        assert del_resp.status_code == 204


@respx.mock
async def test_run_config_success(async_session):
    from app.conf import config
    pipeline_url = f"{config.GITLAB_BASE_URL}/api/v4/projects/{GITLAB_PROJECT_ID}/pipeline"
    respx.post(pipeline_url).mock(
        return_value=httpx.Response(201, json={"id": 77, "status": "pending", "ref": "main", "web_url": ""})
    )

    project_id = await _create_project(async_session)
    app = _make_app(async_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_resp = await client.post(f"/api/v1/projects/{project_id}/configs", json={
            "name": "run-me", "ref": "main", "variables": [],
        })
        config_id = create_resp.json()["id"]

        run_resp = await client.post(f"/api/v1/projects/{project_id}/configs/{config_id}/run")
        assert run_resp.status_code == 200
        data = run_resp.json()
        assert data["pipeline_id"] == 77
        assert data["pipeline_status"] == "pending"


async def test_configs_project_not_found(async_session):
    app = _make_app(async_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/api/v1/projects/{uuid.uuid4()}/configs")
        assert resp.status_code == 404
