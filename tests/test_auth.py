import respx
import httpx
import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from app.auth.middleware import GitLabAuthMiddleware
from app.conf import config

GITLAB_USER_URL = f"{config.GITLAB_BASE_URL.rstrip('/')}/api/v4/user"


def _make_app():
    async def endpoint(request: Request):
        return JSONResponse({
            "user_id": request.state.user_id,
            "token": request.state.gitlab_token,
        })

    async def health(request: Request):
        return JSONResponse({"status": "ok"})

    app = Starlette(routes=[
        Route("/health", health),
        Route("/api/test", endpoint),
    ])
    app.add_middleware(GitLabAuthMiddleware)
    return app


@respx.mock
def test_middleware_valid_token():
    respx.get(GITLAB_USER_URL).mock(
        return_value=httpx.Response(200, json={"id": 77, "username": "alice"})
    )
    client = TestClient(_make_app(), raise_server_exceptions=True)
    resp = client.get("/api/test", headers={"PRIVATE-TOKEN": "glpat-valid"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_id"] == 77
    assert data["token"] == "glpat-valid"


@respx.mock
def test_middleware_invalid_token_returns_401():
    respx.get(GITLAB_USER_URL).mock(return_value=httpx.Response(401, json={"message": "401 Unauthorized"}))
    client = TestClient(_make_app(), raise_server_exceptions=True)
    resp = client.get("/api/test", headers={"PRIVATE-TOKEN": "bad-token"})
    assert resp.status_code == 401


def test_middleware_missing_token_returns_401():
    client = TestClient(_make_app(), raise_server_exceptions=True)
    resp = client.get("/api/test")
    assert resp.status_code == 401


def test_middleware_skips_health():
    client = TestClient(_make_app(), raise_server_exceptions=True)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
