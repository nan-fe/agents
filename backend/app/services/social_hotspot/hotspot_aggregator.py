"""LLM 整合各平台热点素材。"""

from __future__ import annotations

import json
import re
import uuid
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel, Field

from app.config import settings
from app.models.schemas import (
    HotspotAnalysisResult,
    HotspotItem,
    HotspotPlatform,
    HotspotTrend,
    PlatformStat,
    TrendPoint,
)
from app.security.prompt_rules import COMMON_SECURITY_PROMPT
from app.utils.llm_factory import llm_factory

_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")

_PROMOTION_KEYWORDS = (
    "商品、产品、品牌、营销、推广、种草、带货、联名、新品、爆款、"
    "折扣、促销、广告、直播间、测评、开箱、好物推荐"
)


class _LlmHotspotItem(BaseModel):
    platform: HotspotPlatform
    title: str
    summary: str
    promotion_relevance: str = ""
    heat_score: int = Field(ge=0, le=100)
    trend: HotspotTrend = "unknown"
    source_url: str
    published_at: str | None = None
    tags: list[str] = Field(default_factory=list)
    suspicious: bool = False


class _LlmSynthesisOutput(BaseModel):
    summary: str
    cross_platform_hotspots: list[str] = Field(default_factory=list)
    marketing_insights: list[str] = Field(default_factory=list)
    data_source_notes: str = ""


class _LlmPlatformOutput(BaseModel):
    hotspots: list[_LlmHotspotItem] = Field(default_factory=list)


_PLATFORM_LABELS: dict[str, str] = {
    "weibo": "微博",
    "xhs": "小红书",
    "douyin": "抖音",
    "x": "X（Twitter）",
    "reddit": "Reddit",
}


_PLATFORM_AGGREGATOR_PROMPT = PromptTemplate(
    input_variables=["keyword", "platform", "platform_label", "report_date"],
    template="""
【角色设定】
你是一名精通社交媒体营销与消费趋势的数据分析师，擅长识别与「商品宣传、产品推广、品牌营销」相关的热点。

"""
    + COMMON_SECURITY_PROMPT
    + """

【任务】
分析 {platform_label} 平台上与商品宣传密切相关的热点（最近 24～48 小时）。
检索主题：{keyword}
报告日期：{report_date}

【输入数据】
{snippets_section}

【要求】
1. 优先依据检索片段；筛选与商品宣传相关的关键词："""
    + _PROMOTION_KEYWORDS
    + """。
2. 若片段不足，可基于公开信息推断，并在每条 summary 末尾标注「（基于历史数据模拟）」。
3. 提炼 3～5 个热点，字段 platform 固定为 {platform}。
4. source_url 必须来自输入片段 url；无链接可留空，不得编造域名。
5. 全部使用中文。

{format_instructions}
""",
)


_SYNTHESIS_PROMPT = PromptTemplate(
    input_variables=["keyword", "platforms", "hotspots_json", "report_date"],
    template="""
【角色设定】
你是社交媒体营销分析师，请基于各平台已提炼的热点，生成跨平台总结与营销建议。

"""
    + COMMON_SECURITY_PROMPT
    + """

检索主题：{keyword}
分析平台：{platforms}
报告日期：{report_date}

【各平台热点摘要】
{hotspots_json}

【输出要求】
仅输出合法 JSON：
- summary：商品宣传多平台热点速报总览（200 字内）
- cross_platform_hotspots：跨平台共性热点 2～3 条（含传播逻辑）
- marketing_insights：营销价值洞察 3～5 条
- data_source_notes：数据来源及可信度说明

全部使用中文。

{format_instructions}
""",
)


def _snippets_section(snippets_json: str, has_snippets: bool) -> str:
    if has_snippets:
        return (
            "以下为 DuckDuckGo 检索到的公开网页片段（JSON 数组，每条含 platform/title/url/snippet/date）。"
            "你只能依据这些片段中的 URL，不得编造链接。\n\n"
            f"{snippets_json}"
        )
    return (
        "当前无可用检索片段。请基于可获取的公开信息推断近期典型热点，"
        "并在 data_source_notes 标注「基于历史数据模拟」。"
    )


def _normalize_url(url: str) -> str:
    return url.strip().rstrip("/")


def _extract_date(raw: str | None) -> str | None:
    if not raw:
        return None
    match = _DATE_RE.search(raw)
    return match.group(1) if match else None


def _build_allowed_urls(snippets: list[dict[str, Any]]) -> set[str]:
    allowed: set[str] = set()
    for item in snippets:
        url = _normalize_url(str(item.get("url") or ""))
        if url:
            allowed.add(url)
    return allowed


def _validate_hotspots(
    llm_items: list[_LlmHotspotItem],
    *,
    allowed_urls: set[str],
    snippets: list[dict[str, Any]],
) -> list[HotspotItem]:
    snippet_dates = {
        _normalize_url(str(s.get("url") or "")): _extract_date(str(s.get("date") or ""))
        for s in snippets
    }
    seen: set[tuple[str, str]] = set()
    validated: list[HotspotItem] = []

    for item in llm_items:
        url = _normalize_url(item.source_url)
        if allowed_urls:
            if url and url not in allowed_urls:
                continue
            if not url:
                continue
        dedupe_key = (item.platform, item.title.strip().lower())
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        heat = max(0, min(100, int(item.heat_score)))
        published = item.published_at or snippet_dates.get(url)
        validated.append(
            HotspotItem(
                id=uuid.uuid4().hex[:12],
                platform=item.platform,
                title=item.title.strip(),
                summary=item.summary.strip(),
                promotion_relevance=item.promotion_relevance.strip(),
                heat_score=heat,
                trend=item.trend,
                source_url=url,
                published_at=published,
                tags=[t.strip() for t in item.tags if t.strip()],
                suspicious=item.suspicious,
            )
        )
    return validated


def _compute_trend_series(hotspots: list[HotspotItem]) -> list[TrendPoint]:
    by_date: dict[str, list[int]] = defaultdict(list)
    for item in hotspots:
        day = _extract_date(item.published_at)
        if day:
            by_date[day].append(item.heat_score)
    if not by_date:
        return []
    points: list[TrendPoint] = []
    for day in sorted(by_date.keys()):
        scores = by_date[day]
        points.append(
            TrendPoint(
                date=day,
                count=len(scores),
                avg_heat=round(sum(scores) / len(scores), 1),
            )
        )
    return points


def _compute_platform_stats(hotspots: list[HotspotItem]) -> list[PlatformStat]:
    by_platform: dict[str, list[int]] = defaultdict(list)
    for item in hotspots:
        by_platform[item.platform].append(item.heat_score)
    stats: list[PlatformStat] = []
    for platform in sorted(by_platform.keys()):
        scores = by_platform[platform]
        stats.append(
            PlatformStat(
                platform=platform,  # type: ignore[arg-type]
                count=len(scores),
                avg_heat=round(sum(scores) / len(scores), 1),
            )
        )
    return stats


def _build_result(
    *,
    keyword: str,
    platforms: list[str],
    hotspots: list[HotspotItem],
    summary: str,
    cross_platform_hotspots: list[str],
    marketing_insights: list[str],
    data_source_notes: str,
    partial_errors: dict[str, str],
) -> HotspotAnalysisResult:
    return HotspotAnalysisResult(
        keyword=keyword,
        generated_at=datetime.now(UTC),
        platforms=platforms,  # type: ignore[arg-type]
        summary=summary,
        hotspots=hotspots,
        trend_series=_compute_trend_series(hotspots),
        platform_stats=_compute_platform_stats(hotspots),
        cross_platform_hotspots=cross_platform_hotspots,
        marketing_insights=marketing_insights,
        data_source_notes=data_source_notes,
        partial_errors=partial_errors,
    )


def _fallback_platform_hotspots(
    *,
    platform: HotspotPlatform,
    snippets: list[dict[str, Any]],
    keyword: str,
) -> list[HotspotItem]:
    items: list[HotspotItem] = []
    for snippet in snippets[:5]:
        url = _normalize_url(str(snippet.get("url") or ""))
        if not url:
            continue
        items.append(
            HotspotItem(
                id=uuid.uuid4().hex[:12],
                platform=platform,
                title=str(snippet.get("title") or "未命名热点")[:200],
                summary=str(snippet.get("snippet") or "")[:500],
                promotion_relevance="基于检索片段自动收录，待人工研判宣传价值",
                heat_score=50,
                trend="unknown",
                source_url=url,
                published_at=_extract_date(str(snippet.get("date") or "")),
                tags=[keyword],
            )
        )
    return items


async def aggregate_platform_hotspots(
    *,
    platform: HotspotPlatform,
    snippets: list[dict[str, Any]],
    keyword: str,
) -> list[HotspotItem]:
    """单平台大模型热点提炼，供 SSE 阶段性推送。"""
    allowed_urls = _build_allowed_urls(snippets)
    has_snippets = bool(snippets)
    parser = JsonOutputParser(pydantic_object=_LlmPlatformOutput)
    snippets_payload = json.dumps(snippets, ensure_ascii=False, indent=2) if snippets else "[]"
    report_date = datetime.now(UTC).strftime("%Y-%m-%d")
    snippets_section = _snippets_section(snippets_payload, has_snippets)
    platform_label = _PLATFORM_LABELS.get(platform, platform)
    prompt = _PLATFORM_AGGREGATOR_PROMPT.partial(
        format_instructions=parser.get_format_instructions(),
        snippets_section=snippets_section,
    )

    try:
        raw = await llm_factory.run_chain_with_dynamic_tokens(
            prompt_template=prompt,
            chain_input={
                "keyword": keyword,
                "platform": platform,
                "platform_label": platform_label,
                "report_date": report_date,
            },
            parser=parser,
            model_name=settings.BASE_MODEL,
            temperature=0.3,
            agent_name="HotspotPlatformAggregator",
            prompt_version="v1",
        )
        if isinstance(raw, _LlmPlatformOutput):
            llm_output = raw
        elif isinstance(raw, dict):
            llm_output = _LlmPlatformOutput.model_validate(raw)
        else:
            llm_output = _LlmPlatformOutput.model_validate(raw)
    except Exception:
        return _fallback_platform_hotspots(platform=platform, snippets=snippets, keyword=keyword)

    hotspots = _validate_hotspots(
        llm_output.hotspots,
        allowed_urls=allowed_urls,
        snippets=snippets,
    )
    if hotspots:
        return hotspots
    return _fallback_platform_hotspots(platform=platform, snippets=snippets, keyword=keyword)


async def aggregate_synthesis(
    *,
    keyword: str,
    platforms: list[str],
    hotspots: list[HotspotItem],
    partial_errors: dict[str, str],
) -> _LlmSynthesisOutput:
    """跨平台总结与营销洞察。"""
    condensed = [
        {
            "platform": item.platform,
            "title": item.title,
            "summary": item.summary,
            "promotion_relevance": item.promotion_relevance,
        }
        for item in hotspots
    ]
    parser = JsonOutputParser(pydantic_object=_LlmSynthesisOutput)
    prompt = _SYNTHESIS_PROMPT.partial(format_instructions=parser.get_format_instructions())
    report_date = datetime.now(UTC).strftime("%Y-%m-%d")

    try:
        raw = await llm_factory.run_chain_with_dynamic_tokens(
            prompt_template=prompt,
            chain_input={
                "keyword": keyword,
                "platforms": ", ".join(platforms),
                "hotspots_json": json.dumps(condensed, ensure_ascii=False, indent=2),
                "report_date": report_date,
            },
            parser=parser,
            model_name=settings.BASE_MODEL,
            temperature=0.3,
            agent_name="HotspotSynthesis",
            prompt_version="v1",
        )
        if isinstance(raw, _LlmSynthesisOutput):
            return raw
        if isinstance(raw, dict):
            return _LlmSynthesisOutput.model_validate(raw)
        return _LlmSynthesisOutput.model_validate(raw)
    except Exception:
        summary = f"已汇总 {len(hotspots)} 条商品宣传相关热点。"
        if partial_errors:
            summary += f" 部分平台检索失败：{', '.join(partial_errors.keys())}。"
        notes = "数据来自公开检索片段与大模型整合；时效性与完整性有限。"
        if partial_errors:
            notes += f" 失败平台：{', '.join(partial_errors.keys())}。"
        return _LlmSynthesisOutput(summary=summary, data_source_notes=notes)


def build_analysis_result(
    *,
    keyword: str,
    platforms: list[str],
    hotspots: list[HotspotItem],
    synthesis: _LlmSynthesisOutput,
    partial_errors: dict[str, str],
) -> HotspotAnalysisResult:
    return _build_result(
        keyword=keyword,
        platforms=platforms,
        hotspots=hotspots,
        summary=synthesis.summary.strip()[:800],
        cross_platform_hotspots=[s.strip() for s in synthesis.cross_platform_hotspots if s.strip()],
        marketing_insights=[s.strip() for s in synthesis.marketing_insights if s.strip()],
        data_source_notes=synthesis.data_source_notes.strip()[:1000],
        partial_errors=partial_errors,
    )
