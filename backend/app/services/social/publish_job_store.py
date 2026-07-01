"""进程内微博发布任务状态存储。"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PublishJobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass
class PublishJob:
    job_id: str
    platform: str
    status: PublishJobStatus = PublishJobStatus.PENDING
    progress: list[str] = field(default_factory=list)
    post_url: str | None = None
    error: str | None = None
    screenshot_path: str | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    payload_summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "platform": self.platform,
            "status": self.status.value,
            "progress": list(self.progress),
            "post_url": self.post_url,
            "error": self.error,
            "screenshot_path": self.screenshot_path,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "payload_summary": dict(self.payload_summary),
        }


class PublishJobStore:
    def __init__(self, *, retention_seconds: float = 3600.0) -> None:
        self._jobs: dict[str, PublishJob] = {}
        self._lock = asyncio.Lock()
        self._retention_seconds = retention_seconds

    async def create_job(
        self,
        *,
        platform: str,
        payload_summary: dict[str, Any] | None = None,
    ) -> PublishJob:
        job_id = uuid.uuid4().hex
        job = PublishJob(
            job_id=job_id,
            platform=platform,
            payload_summary=payload_summary or {},
        )
        async with self._lock:
            self._jobs[job_id] = job
            await self._reap_locked()
        return job

    async def get_job(self, job_id: str) -> PublishJob | None:
        async with self._lock:
            return self._jobs.get(job_id)

    async def append_progress(self, job_id: str, message: str) -> None:
        async with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            job.progress.append(message)
            job.updated_at = time.time()

    async def mark_running(self, job_id: str) -> None:
        async with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            job.status = PublishJobStatus.RUNNING
            job.updated_at = time.time()

    async def mark_succeeded(self, job_id: str, *, post_url: str | None = None) -> None:
        async with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            job.status = PublishJobStatus.SUCCEEDED
            job.post_url = post_url
            job.updated_at = time.time()

    async def mark_failed(
        self,
        job_id: str,
        *,
        error: str,
        screenshot_path: str | None = None,
    ) -> None:
        async with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            job.status = PublishJobStatus.FAILED
            job.error = error
            job.screenshot_path = screenshot_path
            job.updated_at = time.time()

    async def _reap_locked(self) -> None:
        cutoff = time.time() - self._retention_seconds
        stale = [
            jid
            for jid, job in self._jobs.items()
            if job.updated_at < cutoff
            and job.status in {PublishJobStatus.SUCCEEDED, PublishJobStatus.FAILED}
        ]
        for jid in stale:
            self._jobs.pop(jid, None)


publish_job_store = PublishJobStore()
