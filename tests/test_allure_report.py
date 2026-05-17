import io
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.features.pipelines.allure_report import (
    AllureStatus,
    _extract_allure_results,
    generate_report,
    get_report_status,
    report_url,
)
from app.features.pipelines.crud import upsert_allure_report_status

PIPELINE_ID = 55
GITLAB_PROJECT_ID = 100
ALLURE_PATH = "allure-results"


def _make_zip(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buf.getvalue()


# --- get_report_status ---

async def test_get_report_status_not_started(async_session):
    status = await get_report_status(async_session, pipeline_id=999)
    assert status == "not_started"


async def test_get_report_status_pending(async_session):
    await upsert_allure_report_status(async_session, PIPELINE_ID, GITLAB_PROJECT_ID, "pending")
    status = await get_report_status(async_session, PIPELINE_ID)
    assert status == "pending"


async def test_get_report_status_ready(async_session):
    await upsert_allure_report_status(async_session, PIPELINE_ID, GITLAB_PROJECT_ID, "ready")
    status = await get_report_status(async_session, PIPELINE_ID)
    assert status == "ready"


async def test_get_report_status_error(async_session):
    await upsert_allure_report_status(
        async_session, PIPELINE_ID, GITLAB_PROJECT_ID, "error", error_text="oops"
    )
    status = await get_report_status(async_session, PIPELINE_ID)
    assert status == "error"


# --- _extract_allure_results ---

def test_extract_allure_results(tmp_path):
    zip_bytes = _make_zip({
        "allure-results/test-result.json": b'{"name": "test"}',
        "allure-results/environment.properties": b"ENV=prod",
        "other-dir/ignore.txt": b"skip me",
    })

    with patch("app.features.pipelines.allure_report.config") as mock_cfg:
        mock_cfg.REPORTS_DIR = str(tmp_path)
        results_dir = _extract_allure_results(zip_bytes, pipeline_id=1, allure_results_path="allure-results")

    assert (results_dir / "test-result.json").exists()
    assert (results_dir / "environment.properties").exists()
    assert not (results_dir / "ignore.txt").exists()


def test_extract_custom_path(tmp_path):
    zip_bytes = _make_zip({
        "artifacts/allure-results/r.json": b"{}",
        "allure-results/skip.json": b"{}",
    })

    with patch("app.features.pipelines.allure_report.config") as mock_cfg:
        mock_cfg.REPORTS_DIR = str(tmp_path)
        results_dir = _extract_allure_results(
            zip_bytes, pipeline_id=2, allure_results_path="artifacts/allure-results"
        )

    assert (results_dir / "r.json").exists()
    assert not (results_dir / "skip.json").exists()


# --- generate_report — now opens its own session via async_session_factory ---

async def test_generate_report_success(async_session, tmp_path):
    zip_bytes = _make_zip({"allure-results/r.json": b"{}"})

    mock_client = AsyncMock()
    mock_client.download_job_artifacts.return_value = zip_bytes

    with (
        patch("app.features.pipelines.allure_report.config") as mock_cfg,
        patch("app.features.pipelines.allure_report._run_allure_generate", new=AsyncMock()),
        patch("app.features.pipelines.allure_report.async_session_factory") as mock_factory,
    ):
        mock_cfg.REPORTS_DIR = str(tmp_path)
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=async_session)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
        await generate_report(mock_client, PIPELINE_ID, job_id=7, gitlab_project_id=GITLAB_PROJECT_ID, allure_results_path=ALLURE_PATH)

    status = await get_report_status(async_session, PIPELINE_ID)
    assert status == "ready"


async def test_generate_report_failure(async_session, tmp_path):
    mock_client = AsyncMock()
    mock_client.download_job_artifacts.side_effect = RuntimeError("network error")

    with (
        patch("app.features.pipelines.allure_report.config") as mock_cfg,
        patch("app.features.pipelines.allure_report.async_session_factory") as mock_factory,
    ):
        mock_cfg.REPORTS_DIR = str(tmp_path)
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=async_session)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
        await generate_report(mock_client, PIPELINE_ID, job_id=7, gitlab_project_id=GITLAB_PROJECT_ID, allure_results_path=ALLURE_PATH)

    status = await get_report_status(async_session, PIPELINE_ID)
    assert status == "error"


# --- report_url ---

def test_report_url():
    url = report_url(42)
    assert "42" in url
    assert url.startswith("/")
