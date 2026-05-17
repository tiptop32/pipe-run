import logging

import httpx
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.conf import config

log = logging.getLogger(__name__)

_SKIP_PATHS = {"/", "/health", "/favicon.ico"}
_SKIP_PREFIXES = ("/static",)


class GitLabAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if path in _SKIP_PATHS or any(path.startswith(p) for p in _SKIP_PREFIXES):
            return await call_next(request)

        token = request.headers.get("PRIVATE-TOKEN")
        if not token:
            return JSONResponse({"detail": "Missing PRIVATE-TOKEN header"}, status_code=401)

        user_id = await _resolve_user_id(token)
        if user_id is None:
            return JSONResponse({"detail": "Invalid GitLab token"}, status_code=401)

        request.state.user_id = user_id
        request.state.gitlab_token = token
        return await call_next(request)


async def _resolve_user_id(token: str) -> int | None:
    url = f"{config.GITLAB_BASE_URL.rstrip('/')}/api/v4/user"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, headers={"PRIVATE-TOKEN": token})
        if resp.status_code == 200:
            return resp.json().get("id")
    except httpx.RequestError as exc:
        log.warning("GitLab reachability check failed: %s", exc)
    return None
