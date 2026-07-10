"""社交媒体热点分析结果缓存。"""

from __future__ import annotations

import asyncio
import time

from app.models.schemas import HotspotAnalysisResult


class HotspotResultCache:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._cache: dict[str, tuple[float, HotspotAnalysisResult]] = {}

    def _cache_key(self, keyword: str, platforms: list[str]) -> str:
        return f"{keyword.strip().lower()}|{','.join(sorted(platforms))}"

    async def get_cached_result(
        self,
        keyword: str,
        platforms: list[str],
        *,
        ttl_seconds: float,
    ) -> HotspotAnalysisResult | None:
        key = self._cache_key(keyword, platforms)
        async with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            cached_at, result = entry
            if time.time() - cached_at > ttl_seconds:
                self._cache.pop(key, None)
                return None
            return result

    async def set_cached_result(
        self,
        keyword: str,
        platforms: list[str],
        result: HotspotAnalysisResult,
    ) -> None:
        key = self._cache_key(keyword, platforms)
        async with self._lock:
            self._cache[key] = (time.time(), result)


hotspot_job_store = HotspotResultCache()
