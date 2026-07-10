"""社交媒体热点分析 API 测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app
from app.memory.db import close_db, init_db
from app.models.schemas import HotspotAnalysisResult, HotspotItem


@pytest.fixture(autouse=True)
def memory_db(monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_URL", "sqlite+aiosqlite:///:memory:")


@pytest.fixture(autouse=True)
def enable_hotspot():
    settings.SOCIAL_HOTSPOT_ENABLED = True


async def _collect_hotspot_sse_events(response) -> list[dict]:
    import json

    events: list[dict] = []
    current_data: str | None = None

    async for line in response.aiter_lines():
        if line.startswith("data:"):
            current_data = line.split(":", 1)[1].strip()
            continue
        if not line.strip() and current_data is not None:
            events.append(json.loads(current_data))
            current_data = None

    if current_data is not None:
        events.append(json.loads(current_data))
    return events


@pytest.mark.asyncio
async def test_hotspot_analyze_sse_stream() -> None:
    await close_db()
    await init_db()

    mock_hotspot = HotspotItem(
        id="h1",
        platform="weibo",
        title="测试热点",
        summary="摘要",
        promotion_relevance="用户种草",
        heat_score=70,
        trend="rising",
        source_url="https://example.com/1",
    )
    mock_result = HotspotAnalysisResult(
        keyword="商品宣传",
        generated_at="2026-07-10T00:00:00Z",
        platforms=["weibo"],
        summary="总览",
        hotspots=[mock_hotspot],
        cross_platform_hotspots=["跨平台话题"],
        marketing_insights=["洞察建议"],
        data_source_notes="说明",
    )

    from app.services.social_hotspot.hotspot_aggregator import _LlmSynthesisOutput

    with (
        patch(
            "app.services.social_hotspot.hotspot_service.hotspot_job_store.get_cached_result",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.services.social_hotspot.hotspot_service.hotspot_job_store.set_cached_result",
            new=AsyncMock(),
        ),
        patch(
            "app.services.social_hotspot.hotspot_service.aggregate_platform_hotspots",
            new=AsyncMock(return_value=[mock_hotspot]),
        ),
        patch(
            "app.services.social_hotspot.hotspot_service.aggregate_synthesis",
            new=AsyncMock(
                return_value=_LlmSynthesisOutput(
                    summary="总览",
                    cross_platform_hotspots=["跨平台话题"],
                    marketing_insights=["洞察建议"],
                    data_source_notes="说明",
                )
            ),
        ),
        patch(
            "app.services.social_hotspot.hotspot_service.build_analysis_result",
            return_value=mock_result,
        ),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            async with client.stream(
                "POST",
                "/social-hotspots/analyze/stream",
                json={"platforms": ["weibo"]},
            ) as response:
                assert response.status_code == 200
                events = await _collect_hotspot_sse_events(response)

    event_types = [event["type"] for event in events]
    assert "log" in event_types
    assert "platform_hotspots" in event_types
    assert "summary" in event_types
    assert "result" in event_types
    result_event = next(event for event in events if event["type"] == "result")
    assert result_event["data"]["summary"] == "总览"


@pytest.mark.asyncio
async def test_hotspot_disabled_returns_503() -> None:
    await close_db()
    await init_db()
    settings.SOCIAL_HOTSPOT_ENABLED = False
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/social-hotspots/analyze/stream",
            json={"keyword": "护肤", "platforms": ["weibo"]},
        )
        assert resp.status_code == 503
