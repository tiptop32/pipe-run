import logging
import time

import httpx
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.conf import config

log = logging.getLogger(__name__)

_SKIP_PATHS = {"/", "/health", "/favicon.ico"}
_SKIP_PREFIXES = ("/static",)

# token hash → (user_id, expires_monotonic)
_token_cache: dict[int, tuple[int, float]] = {}
_CACHE_TTL = 60.0
_CACHE_MAX = 1000


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
    key = hash(token)
    now = time.monotonic()

    entry = _token_cache.get(key)
    if entry is not None:
        user_id, expires_at = entry
        if now < expires_at:
            return user_id
        del _token_cache[key]

    user_id = await _fetch_user_id(token)
    if user_id is not None:
        if len(_token_cache) >= _CACHE_MAX:
            _token_cache.clear()
        _token_cache[key] = (user_id, now + _CACHE_TTL)
    return user_id


async def _fetch_user_id(token: str) -> int | None:
    url = f"{config.GITLAB_BASE_URL.rstrip('/')}/api/v4/user"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, headers={"PRIVATE-TOKEN": token})
        if resp.status_code == 200:
            return resp.json().get("id")
    except httpx.RequestError as exc:
        log.warning("GitLab reachability check failed: %s", exc)
    return None
