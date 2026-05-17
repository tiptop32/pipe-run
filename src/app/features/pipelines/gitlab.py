import logging

import httpx

from app.features.pipelines.schemas import Job, Pipeline, Schedule, Variable

log = logging.getLogger(__name__)

TERMINAL_STATUSES = {"success", "failed", "canceled", "skipped"}


class GitLabAPIError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"GitLab API error {status_code}: {message}")


class GitLabClient:
    def __init__(self, base_url: str, access_token: str, project_id: int, verify_ssl: bool = True):
        self._base = base_url.rstrip("/")
        self._headers = {"PRIVATE-TOKEN": access_token}
        self._project_id = project_id
        # single client per instance — reuses TLS connections within one request lifecycle
        self._client = httpx.AsyncClient(
            verify=verify_ssl,
            follow_redirects=True,
            timeout=httpx.Timeout(30.0),
        )

    def _project_url(self, path: str) -> str:
        return f"{self._base}/api/v4/projects/{self._project_id}/{path.lstrip('/')}"

    async def _get(self, url: str, **kwargs) -> dict | list:
        resp = await self._client.get(url, headers=self._headers, **kwargs)
        if not resp.is_success:
            raise GitLabAPIError(resp.status_code, resp.text)
        return resp.json()

    async def _get_bytes(self, url: str, **kwargs) -> bytes:
        resp = await self._client.get(url, headers=self._headers, **kwargs)
        if not resp.is_success:
            raise GitLabAPIError(resp.status_code, resp.text)
        return resp.content

    async def _post(self, url: str, **kwargs) -> dict:
        resp = await self._client.post(url, headers=self._headers, **kwargs)
        if not resp.is_success:
            raise GitLabAPIError(resp.status_code, resp.text)
        return resp.json()

    async def get_branches(self) -> list[str]:
        data = await self._get(self._project_url("repository/branches"), params={"per_page": 100})
        return [b["name"] for b in data]

    async def get_pipeline(self, pipeline_id: int) -> Pipeline:
        data = await self._get(self._project_url(f"pipelines/{pipeline_id}"))
        return Pipeline(
            id=data["id"],
            status=data["status"],
            ref=data.get("ref", ""),
            web_url=data.get("web_url", ""),
        )

    async def run_pipeline(self, ref: str, variables: list[dict]) -> Pipeline:
        payload = {"ref": ref, "variables": variables}
        data = await self._post(self._project_url("pipeline"), json=payload)
        return Pipeline(
            id=data["id"],
            status=data.get("status", "pending"),
            ref=data.get("ref", ref),
            web_url=data.get("web_url", ""),
        )

    async def get_jobs(self, pipeline_id: int) -> list[Job]:
        data = await self._get(
            self._project_url(f"pipelines/{pipeline_id}/jobs"),
            params={"per_page": 100},
        )
        return [
            Job(
                id=j["id"],
                name=j.get("name", ""),
                status=j.get("status", ""),
                web_url=j.get("web_url", ""),
                has_artifacts=bool(j.get("artifacts_file")),
            )
            for j in data
        ]

    async def download_job_artifacts(self, job_id: int) -> bytes:
        return await self._get_bytes(self._project_url(f"jobs/{job_id}/artifacts"))

    async def get_pipeline_schedules(self) -> list[Schedule]:
        data = await self._get(self._project_url("pipeline_schedules"))
        return [Schedule(id=s["id"], description=s.get("description", ""), ref=s["ref"]) for s in data]

    async def get_schedule(self, schedule_id: int) -> Schedule:
        data = await self._get(self._project_url(f"pipeline_schedules/{schedule_id}"))
        variables = [
            Variable(key=v["key"], value=v["value"], variable_type=v.get("variable_type", "env_var"))
            for v in data.get("variables") or []
        ]
        return Schedule(
            id=data["id"],
            description=data.get("description", ""),
            ref=data["ref"],
            variables=variables,
        )

    async def search_schedules(self, query: str) -> list[Schedule]:
        data = await self._get(self._project_url("pipeline_schedules"), params={"per_page": 100})
        q = query.lower()
        return [
            Schedule(id=s["id"], description=s.get("description", ""), ref=s["ref"])
            for s in data
            if q in s.get("description", "").lower()
        ]

    async def get_schedule_last_pipeline(self, schedule_id: int) -> Pipeline | None:
        try:
            data = await self._get(
                self._project_url(f"pipeline_schedules/{schedule_id}/pipelines"),
                params={"per_page": 1, "order_by": "id", "sort": "desc"},
            )
        except GitLabAPIError:
            return None
        if not data:
            return None
        p = data[0]
        return Pipeline(
            id=p["id"],
            status=p.get("status", ""),
            ref=p.get("ref", ""),
            web_url=p.get("web_url", ""),
            created_at=p.get("created_at", ""),
        )

    async def run_pipeline_schedule(self, schedule_id: int) -> Pipeline:
        data = await self._post(self._project_url(f"pipeline_schedules/{schedule_id}/play"))
        return Pipeline(id=data.get("id", 0), status="pending", ref="")
