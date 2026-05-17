import asyncio
import logging
import zipfile
from pathlib import Path
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.conf import config
from app.features.pipelines.crud import get_allure_report_status, upsert_allure_report_status
from app.features.pipelines.gitlab import GitLabClient

log = logging.getLogger(__name__)

AllureStatus = Literal["not_started", "pending", "ready", "error"]


async def get_report_status(session: AsyncSession, pipeline_id: int) -> AllureStatus:
    report = await get_allure_report_status(session, pipeline_id)
    if report is None:
        return "not_started"
    return report.status  # type: ignore[return-value]


async def generate_report(
    session: AsyncSession,
    gitlab_client: GitLabClient,
    pipeline_id: int,
    job_id: int,
    gitlab_project_id: int,
) -> None:
    await upsert_allure_report_status(session, pipeline_id, gitlab_project_id, "pending")
    try:
        zip_bytes = await gitlab_client.download_job_artifacts(job_id)
        report_dir = _report_dir(pipeline_id)
        results_dir = _extract_allure_results(zip_bytes, pipeline_id)
        await _run_allure_generate(results_dir, report_dir)
        await upsert_allure_report_status(session, pipeline_id, gitlab_project_id, "ready")
    except Exception as exc:
        log.error("Allure generation failed for pipeline %d: %s", pipeline_id, exc)
        await upsert_allure_report_status(
            session, pipeline_id, gitlab_project_id, "error", error_text=str(exc)
        )


def report_url(pipeline_id: int) -> str:
    return f"/static/allure_reports/{pipeline_id}/index.html"


def _report_dir(pipeline_id: int) -> Path:
    return Path(config.REPORTS_DIR) / str(pipeline_id)


def _extract_allure_results(zip_bytes: bytes, pipeline_id: int) -> Path:
    results_dir = Path(config.REPORTS_DIR) / f"{pipeline_id}_results"
    results_dir.mkdir(parents=True, exist_ok=True)

    import io
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for member in zf.namelist():
            # extract only files inside allure-results/ directory
            if "allure-results/" in member and not member.endswith("/"):
                filename = Path(member).name
                data = zf.read(member)
                (results_dir / filename).write_bytes(data)

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
