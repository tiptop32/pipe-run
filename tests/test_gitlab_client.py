import pytest
import respx
import httpx

from app.features.pipelines.gitlab import GitLabClient, GitLabAPIError

BASE = "https://gitlab.example.com"
TOKEN = "glpat-test"
PROJECT_ID = 1


def make_client() -> GitLabClient:
    return GitLabClient(base_url=BASE, access_token=TOKEN, project_id=PROJECT_ID)


def project_url(path: str) -> str:
    return f"{BASE}/api/v4/projects/{PROJECT_ID}/{path}"


@respx.mock
async def test_run_pipeline_success():
    respx.post(project_url("pipeline")).mock(
        return_value=httpx.Response(201, json={"id": 42, "status": "pending", "ref": "main", "web_url": ""})
    )
    client = make_client()
    pipeline = await client.run_pipeline("main", [])
    assert pipeline.id == 42
    assert pipeline.status == "pending"


@respx.mock
async def test_run_pipeline_gitlab_error():
    respx.post(project_url("pipeline")).mock(return_value=httpx.Response(400, text="Bad ref"))
    client = make_client()
    with pytest.raises(GitLabAPIError) as exc_info:
        await client.run_pipeline("bad-ref", [])
    assert exc_info.value.status_code == 400


@respx.mock
async def test_get_pipeline():
    respx.get(project_url("pipelines/99")).mock(
        return_value=httpx.Response(200, json={"id": 99, "status": "success", "ref": "main", "web_url": "http://x"})
    )
    client = make_client()
    pipeline = await client.get_pipeline(99)
    assert pipeline.id == 99
    assert pipeline.status == "success"


@respx.mock
async def test_get_jobs():
    respx.get(project_url("pipelines/5/jobs")).mock(
        return_value=httpx.Response(200, json=[
            {"id": 1, "name": "test", "status": "success", "web_url": "", "artifacts_file": {"filename": "a.zip"}},
            {"id": 2, "name": "build", "status": "success", "web_url": "", "artifacts_file": None},
        ])
    )
    client = make_client()
    jobs = await client.get_jobs(5)
    assert len(jobs) == 2
    assert jobs[0].has_artifacts is True
    assert jobs[1].has_artifacts is False


@respx.mock
async def test_get_schedule():
    respx.get(project_url("pipeline_schedules/10")).mock(
        return_value=httpx.Response(200, json={
            "id": 10, "description": "nightly", "ref": "main",
            "variables": [{"key": "ENV", "value": "prod", "variable_type": "env_var"}],
        })
    )
    client = make_client()
    schedule = await client.get_schedule(10)
    assert schedule.id == 10
    assert schedule.description == "nightly"
    assert len(schedule.variables) == 1
    assert schedule.variables[0].key == "ENV"


@respx.mock
async def test_download_job_artifacts():
    respx.get(project_url("jobs/7/artifacts")).mock(
        return_value=httpx.Response(200, content=b"PK\x03\x04")
    )
    client = make_client()
    data = await client.download_job_artifacts(7)
    assert data[:4] == b"PK\x03\x04"


@respx.mock
async def test_get_branches():
    respx.get(project_url("repository/branches")).mock(
        return_value=httpx.Response(200, json=[{"name": "main"}, {"name": "dev"}])
    )
    client = make_client()
    branches = await client.get_branches()
    assert "main" in branches
    assert "dev" in branches


@respx.mock
async def test_search_schedules():
    respx.get(project_url("pipeline_schedules")).mock(
        return_value=httpx.Response(200, json=[
            {"id": 1, "description": "nightly regression", "ref": "main"},
            {"id": 2, "description": "smoke test", "ref": "main"},
        ])
    )
    client = make_client()
    results = await client.search_schedules("night")
    assert len(results) == 1
    assert results[0].id == 1
