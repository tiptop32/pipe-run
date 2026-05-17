import asyncio
import io
import logging
import zipfile
from enum import StrEnum
from pathlib import Path

from app.conf import config
from app.db.base import async_session_factory
from app.features.pipelines.crud import get_allure_report_status, upsert_allure_report_status
from app.features.pipelines.gitlab import GitLabClient

log = logging.getLogger(__name__)


class AllureStatus(StrEnum):
    NOT_STARTED = "not_started"
    PENDING = "pending"
    READY = "ready"
    ERROR = "error"


async def get_report_status(session, pipeline_id: int) -> AllureStatus:
    report = await get_allure_report_status(session, pipeline_id)
    if report is None:
        return AllureStatus.NOT_STARTED
    return AllureStatus(report.status)


async def generate_report(
    gitlab_client: GitLabClient,
    pipeline_id: int,
    job_id: int,
    gitlab_project_id: int,
    allure_results_path: str,
) -> None:
    async with async_session_factory() as session:
        await upsert_allure_report_status(
            session, pipeline_id, gitlab_project_id, AllureStatus.PENDING
        )
        try:
            zip_bytes = await gitlab_client.download_job_artifacts(job_id)
            report_dir = _report_dir(pipeline_id)
            results_dir = _extract_allure_results(zip_bytes, pipeline_id, allure_results_path)
            await _run_allure_generate(results_dir, report_dir)
            await upsert_allure_report_status(
                session, pipeline_id, gitlab_project_id, AllureStatus.READY
            )
        except Exception as exc:
            log.error("Allure generation failed for pipeline %d: %s", pipeline_id, exc)
            await upsert_allure_report_status(
                session, pipeline_id, gitlab_project_id, AllureStatus.ERROR, error_text=str(exc)
            )


def report_url(pipeline_id: int) -> str:
    return f"/static/allure_reports/{pipeline_id}/index.html"


def _report_dir(pipeline_id: int) -> Path:
    return Path(config.REPORTS_DIR) / str(pipeline_id)


def _extract_allure_results(
    zip_bytes: bytes, pipeline_id: int, allure_results_path: str = "allure-results"
) -> Path:
    results_dir = Path(config.REPORTS_DIR) / f"{pipeline_id}_results"
    results_dir.mkdir(parents=True, exist_ok=True)
    results_dir_resolved = results_dir.resolve()

    prefix = allure_results_path.rstrip("/") + "/"
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for member in zf.namelist():
            if not member.startswith(prefix) or member.endswith("/"):
                continue
            filename = Path(member).name
            if not filename:
                continue
            target = (results_dir / filename).resolve()
            # zip slip guard: target must stay inside results_dir
            if not str(target).startswith(str(results_dir_resolved)):
                raise ValueError(f"Zip slip detected in archive member: {member}")
            target.write_bytes(zf.read(member))

    return results_dir


async def _run_allure_generate(results_dir: Path, report_dir: Path) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    proc = await asyncio.create_subprocess_exec(
        "allure", "generate", str(results_dir), "-o", str(report_dir), "--clean",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"allure generate failed: {stderr.decode()}")
