import logging
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from alembic import command
from alembic.config import Config as AlembicConfig
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.auth.middleware import GitLabAuthMiddleware
from app.conf import config
from app.conf.logging import setup_logging
from app.features.gitlab.router import bookmarks_router, router as gitlab_router
from app.features.pipelines.api import router as pipelines_router
from app.features.projects.router import router as projects_router

_STATIC_DIR    = Path(__file__).parent / "static"
_TEMPLATES_DIR = Path(__file__).parent / "templates"

log = logging.getLogger(__name__)


def _run_migrations() -> None:
    alembic_cfg = AlembicConfig("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", config.DATABASE_URL)
    command.upgrade(alembic_cfg, "head")


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(config.LOGLEVEL)
    try:
        _run_migrations()
        log.info("DB migrations applied")
    except Exception as exc:
        log.error("Migration failed: %s", exc)
        raise
    yield


app = FastAPI(title="QA Pipe", lifespan=lifespan)

app.add_middleware(GitLabAuthMiddleware)

app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

app.include_router(projects_router)
app.include_router(pipelines_router)
app.include_router(gitlab_router)
app.include_router(bookmarks_router)


@app.get("/health")
async def health():
    return JSONResponse({"status": "ok"})


@app.get("/")
async def index():
    return FileResponse(str(_TEMPLATES_DIR / "index.html"))


def main() -> None:
    uvicorn.run("app.main:app", host=config.HOST, port=config.PORT, reload=False)
