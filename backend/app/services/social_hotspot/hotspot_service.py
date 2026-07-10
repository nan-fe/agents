"""社交媒体热点分析编排服务。"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

from app.config import settings
from app.models.schemas import (
    DEFAULT_HOTSPOT_KEYWORD,
    DEFAULT_HOTSPOT_PLATFORMS,
    HotspotAnalyzeRequest,
    HotspotItem,
    HotspotPlatform,
    SSEMessage,
)
from app.services.social_hotspot.hotspot_aggregator import (
    aggregate_platform_hotspots,
    aggregate_synthesis,
    build_analysis_result,
)
from app.services.social_hotspot.hotspot_job_store import hotspot_job_store

logger = logging.getLogger(__name__)

_PLATFORM_LABELS: dict[str, str] = {
    "weibo": "微博",
    "xhs": "小红书",
    "douyin": "抖音",
    "x": "X（Twitter）",
    "reddit": "Reddit",
}


def _normalize_platform(platform: str) -> HotspotPlatform:
    if platform in {"weibo", "xhs", "douyin", "x", "reddit"}:
        return platform  # type: ignore[return-value]
    return "weibo"


class HotspotService:
    def _resolve_request(self, payload: HotspotAnalyzeRequest) -> tuple[str, list[str]]:
        keyword = payload.keyword.strip() or DEFAULT_HOTSPOT_KEYWORD
        platforms = list(payload.platforms) or list(DEFAULT_HOTSPOT_PLATFORMS)
        return keyword, platforms

    def _emit_sse(self, event_id: int, event_type: str, data: dict[str, Any]) -> dict[str, Any]:
        message = SSEMessage(type=event_type, data=data)
        return {"event": "message", "data": message.model_dump_json(), "id": str(event_id)}

    async def _push_cached_events(
        self,
        *,
        push,
        cached,
        platforms: list[str],
    ) -> None:
        await push("log", {"message": "命中缓存，正在加载热点速报…"})
        for platform in platforms:
            items = [item for item in cached.hotspots if item.platform == platform]
            await push(
                "platform_hotspots",
                {
                    "platform": platform,
                    "hotspots": [item.model_dump(mode="json") for item in items],
                },
            )
        await push("summary", {"summary": cached.summary})
        if cached.cross_platform_hotspots:
            await push("cross_platform", {"items": cached.cross_platform_hotspots})
        if cached.marketing_insights:
            await push("insights", {"items": cached.marketing_insights})
        if cached.data_source_notes:
            await push("data_source", {"notes": cached.data_source_notes})
        await push("result", cached.model_dump(mode="json"))

    async def _run_stream_worker(
        self,
        payload: HotspotAnalyzeRequest,
        queue: asyncio.Queue[dict[str, Any] | None],
    ) -> None:
        event_id = 1
        push_lock = asyncio.Lock()

        async def push(event_type: str, data: dict[str, Any]) -> None:
            nonlocal event_id
            async with push_lock:
                event_id += 1
                await queue.put(self._emit_sse(event_id, event_type, data))

        try:
            keyword, platforms = self._resolve_request(payload)
            cached = await hotspot_job_store.get_cached_result(
                keyword,
                platforms,
                ttl_seconds=settings.SOCIAL_HOTSPOT_CACHE_TTL_SEC,
            )
            if cached is not None:
                await self._push_cached_events(push=push, cached=cached, platforms=platforms)
                return

            partial_errors: dict[str, str] = {}

            await push(
                "log",
                {"message": "正在调用大模型分析各平台商品宣传热点…"},
            )

            all_hotspots: list[HotspotItem] = []

            async def analyze_platform(platform: str) -> tuple[str, list[HotspotItem]]:
                label = _PLATFORM_LABELS.get(platform, platform)
                platform_key = _normalize_platform(platform)
                await push("log", {"message": f"大模型正在分析 {label} 平台热点…"})
                try:
                    items = await asyncio.wait_for(
                        aggregate_platform_hotspots(
                            platform=platform_key,
                            snippets=[],
                            keyword=keyword,
                        ),
                        timeout=settings.SOCIAL_HOTSPOT_LLM_TIMEOUT_SEC,
                    )
                except Exception as exc:
                    logger.warning("单平台热点分析失败 platform=%s: %s", platform, exc)
                    items = []
                return platform, items

            analysis_tasks = [
                asyncio.create_task(analyze_platform(platform)) for platform in platforms
            ]
            for task in asyncio.as_completed(analysis_tasks):
                platform, items = await task
                label = _PLATFORM_LABELS.get(platform, platform)
                all_hotspots.extend(items)
                await push(
                    "platform_hotspots",
                    {
                        "platform": platform,
                        "label": label,
                        "hotspots": [item.model_dump(mode="json") for item in items],
                    },
                )

            await push("log", {"message": "正在生成跨平台洞察与营销建议…"})
            synthesis = await asyncio.wait_for(
                aggregate_synthesis(
                    keyword=keyword,
                    platforms=platforms,
                    hotspots=all_hotspots,
                    partial_errors=partial_errors,
                ),
                timeout=settings.SOCIAL_HOTSPOT_LLM_TIMEOUT_SEC,
            )

            await push("summary", {"summary": synthesis.summary})
            if synthesis.cross_platform_hotspots:
                await push("cross_platform", {"items": synthesis.cross_platform_hotspots})
            if synthesis.marketing_insights:
                await push("insights", {"items": synthesis.marketing_insights})
            if synthesis.data_source_notes:
                await push("data_source", {"notes": synthesis.data_source_notes})

            result = build_analysis_result(
                keyword=keyword,
                platforms=platforms,
                hotspots=all_hotspots,
                synthesis=synthesis,
                partial_errors=partial_errors,
            )
            await hotspot_job_store.set_cached_result(keyword, platforms, result)
            await push("result", result.model_dump(mode="json"))
        except Exception as exc:
            logger.exception("热点分析 SSE 流失败")
            await push("error", {"message": str(exc)})
        finally:
            await queue.put(None)

    async def stream_analysis_events(
        self,
        payload: HotspotAnalyzeRequest,
    ) -> AsyncIterator[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        asyncio.create_task(self._run_stream_worker(payload, queue))

        yield self._emit_sse(1, "log", {"message": "连接成功，热点分析已启动…"})

        while True:
            event = await queue.get()
            if event is None:
                break
            yield event


hotspot_service = HotspotService()
