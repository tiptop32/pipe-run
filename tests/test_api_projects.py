import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.db.base import get_db_session
from app.features.projects.router import router as projects_router

USER_ID = 42
GITLAB_PROJECT_ID = 100


class FakeAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request.state.user_id = USER_ID
        request.state.gitlab_token = "glpat-fake"
        return await call_next(request)


def _make_app(session):
    app = FastAPI()
    app.add_middleware(FakeAuthMiddleware)
    app.include_router(projects_router)
    app.dependency_overrides[get_db_session] = lambda: session
    return app


async def test_create_and_list_project(async_session):
    app = _make_app(async_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/projects", json={
            "gitlab_project_id": GITLAB_PROJECT_ID,
            "display_name": "My Repo",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["display_name"] == "My Repo"
        assert data["allure_results_path"] is None

        resp2 = await client.get("/api/v1/projects")
        assert resp2.status_code == 200
        items = resp2.json()
        assert len(items) == 1
        assert items[0]["gitlab_project_id"] == GITLAB_PROJECT_ID


async def test_create_project_with_allure_path(async_session):
    app = _make_app(async_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/projects", json={
            "gitlab_project_id": 200,
            "display_name": "Allure Project",
            "allure_results_path": "artifacts/allure-results",
        })
        assert resp.status_code == 201
        assert resp.json()["allure_results_path"] == "artifacts/allure-results"


async def test_delete_project(async_session):
    app = _make_app(async_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_resp = await client.post("/api/v1/projects", json={
            "gitlab_project_id": 300,
            "display_name": "To Delete",
        })
        project_id = create_resp.json()["id"]

        del_resp = await client.delete(f"/api/v1/projects/{project_id}")
        assert del_resp.status_code == 204

        list_resp = await client.get("/api/v1/projects")
        assert list_resp.json() == []


async def test_delete_project_not_found(async_session):
    app = _make_app(async_session)
    import uuid
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.delete(f"/api/v1/projects/{uuid.uuid4()}")
        assert resp.status_code == 404
