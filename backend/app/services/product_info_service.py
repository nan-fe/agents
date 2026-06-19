"""从电商商品链接抓取并结构化商品信息，供选品池与 RAG 索引使用。

采集链路（按优先级）：
1. URL 校验与短链解析 → 规范商品详情页地址
2. Playwright 打开页面、等待渲染 → 提取可见文本 + 截图/详情图
3. 多模态大模型识别图片中的卖点/规格等补充信息
4. httpx 静态抓取与 DuckDuckGo 检索作为回退
5. 文本大模型结构化提取并写入 RAG 商品库
"""

import asyncio
import json
import math
import re
import secrets
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
from bs4 import BeautifulSoup
from langchain_core.prompts import PromptTemplate
from openai import AsyncOpenAI

from app.agents.product_rag_system.agent import ProductRagAgent
from app.agents.product_rag_system.product_database import (
    SEARCH_TEXT_MAX_TOKENS,
    ProductDatabase,
)
from app.agents.product_rag_system.product_scrape_database import (
    DETAIL_IMAGE_SEPARATOR,
    SCRAPE_TEXT_MAX_CHARS,
)
from app.config import settings
from app.models.schemas import (
    ProductComment,
    ProductInfoCreateResponse,
    ProductInfoPreviewResponse,
    ProductItem,
    ProductListResponse,
)
from app.services.product_page_scraper import (
    ProductPageCapture,
    build_vision_image_payload,
    capture_product_page,
    is_jd_blocked_page,
    is_playwright_available,
    is_usable_product_page_text,
    playwright_setup_hint,
    _parse_price_from_visible_text,
    _parse_sales_from_visible_text,
)
from app.utils.llm_factory import llm_factory
from app.utils.search_tool import (
    canonical_taobao_item_url,
    search_duckduckgo_langchain_async,
    search_jd_product_price_snippets,
    search_product_context_snippets,
)
from app.utils.token_counter import token_counter

_SUPPORTED_HOSTS = ("taobao.com", "tmall.com", "jd.com", "jd.hk")
_SHORT_LINK_HOSTS = ("e.tb.cn", "m.tb.cn", "s.click.taobao.com", "u.jd.com", "3.cn")
_JD_ITEM_ID_RE = re.compile(r"/(\d+)\.html")
_TAOBAO_ITEM_ID_RE = re.compile(r"[?&]id=(\d+)")
_MIN_PAGE_TEXT_CHARS = 80
_PREVIEW_COMMENTS_LIMIT = 3


def _elapsed_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

_EXTRACT_PROMPT = PromptTemplate(
    input_variables=["url", "page_text"],
    template="""你是电商商品信息提取助手。根据商品详情页抓取到的文本与图片识别摘要，提取结构化字段。

要求：
1. 仅输出合法 JSON，不要 markdown 代码块。
2. 字段：name（商品名）、category（类别）、description（商品摘要，纯文本无 HTML）、shop_name（店铺名）、price（数字，未知填 0）、sales（销量或评价数整数，未知填 0）。
3. description 需充实完整，建议按以下结构组织（可用换行分隔各段）：
   - 核心卖点：2-4 个最能打动用户的亮点
   - 商品特性：材质、规格、功能、技术等关键参数
   - 适用人群：适合谁、什么场景使用
   - 产品特点：与同类相比的差异化优势
   总长度 300-500 字，去掉导航、促销废话和重复内容，信息尽量具体。
4. 若文本不足以判断某字段，category/shop_name 可用「未分类」「未知店铺」，但 name 不得编造；无法确定 name 时返回 {{"name": ""}}。
5. 禁止输出「未知商品」「无法从页面文本中提取」等占位商品名或敷衍描述。
6. 若上下文含「页面价格」「页面销量」结构化行，必须优先采用其数值；仅当完全无价格/销量线索时才填 0。

商品链接：{url}

页面文本：
{page_text}

JSON：""",
)

_VISION_PROMPT = """你是电商商品详情识别助手。请阅读商品详情页截图与详情图片，提取可用于检索的结构化摘要。

要求：
1. 用中文输出纯文本，不要 JSON。
2. 重点识别：商品名、品牌、品类、核心卖点、规格参数、功能特性、适用人群与使用场景、差异化特点、店铺名（若可见）。
3. 若截图中可见价格（￥数字）或销量/评价数（如「xx条评价」「已售xx」），请单独一行写出：
   - 价格：数字（仅写阿拉伯数字，不含货币符号）
   - 销量：整数（评价数/销量均可）
4. 忽略导航、登录提示、广告横幅等无关信息。
5. 总长度控制在 500 字以内，信息尽量具体、可写入商品摘要。
6. 商品详情包含详细描述、参数、功能、使用方法等，请提炼为可读的卖点与特性描述。

商品链接：{url}
"""


def _is_supported_product_host(host: str) -> bool:
    host = (host or "").lower()
    return any(supported in host for supported in _SUPPORTED_HOSTS)


def _is_allowed_input_host(host: str) -> bool:
    host = (host or "").lower()
    if _is_supported_product_host(host):
        return True
    return any(short in host for short in _SHORT_LINK_HOSTS)


def validate_product_url(url: str) -> str:
    """校验商品链接输入（含短链）。"""
    cleaned = (url or "").strip()
    if not cleaned:
        raise ValueError("商品链接不能为空")

    if not cleaned.startswith(("http://", "https://")):
        cleaned = f"https://{cleaned}"

    parsed = urlparse(cleaned)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("商品链接需以 http:// 或 https:// 开头")

    if not _is_allowed_input_host(parsed.netloc):
        raise ValueError("暂仅支持淘宝、天猫、京东商品链接（含官方短链）")

    return cleaned


def _extract_taobao_item_id(url: str) -> str | None:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    if "id" in query and query["id"]:
        return query["id"][0]
    match = _TAOBAO_ITEM_ID_RE.search(url)
    return match.group(1) if match else None


def _extract_jd_item_id(url: str) -> str | None:
    match = _JD_ITEM_ID_RE.search(url)
    return match.group(1) if match else None


def _canonical_jd_item_url(item_id: str) -> str:
    return f"https://item.jd.com/{item_id}.html"


async def resolve_product_url(url: str) -> str:
    """跟随短链重定向并规范为商品详情页 URL。"""
    started = time.perf_counter()
    cleaned = validate_product_url(url)
    print(f"[ProductInfoService] 解析商品链接 input={cleaned}")

    # 先从原始链接提取 ID（京东/淘宝 httpx 跟随重定向常会落到首页）
    taobao_id = _extract_taobao_item_id(cleaned)
    if taobao_id:
        resolved = canonical_taobao_item_url(cleaned)
        print(
            f"[ProductInfoService] 从原始链接识别淘宝商品 id={taobao_id} "
            f"resolved={resolved} +{_elapsed_ms(started)}ms"
        )
        return resolved

    jd_id = _extract_jd_item_id(cleaned)
    if jd_id:
        resolved = _canonical_jd_item_url(jd_id)
        print(
            f"[ProductInfoService] 从原始链接识别京东商品 id={jd_id} "
            f"resolved={resolved} +{_elapsed_ms(started)}ms"
        )
        return resolved

    redirect_started = time.perf_counter()
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=httpx.Timeout(20.0),
        headers=_DEFAULT_HEADERS,
    ) as client:
        response = await client.get(cleaned)
        response.raise_for_status()
        final_url = str(response.url)
    print(
        f"[ProductInfoService] 短链重定向完成 final_url={final_url} "
        f"+{_elapsed_ms(redirect_started)}ms"
    )

    taobao_id = _extract_taobao_item_id(final_url)
    if taobao_id:
        resolved = canonical_taobao_item_url(final_url)
        print(f"[ProductInfoService] 重定向后识别淘宝商品 resolved={resolved}")
        return resolved

    jd_id = _extract_jd_item_id(final_url)
    if jd_id:
        resolved = _canonical_jd_item_url(jd_id)
        print(f"[ProductInfoService] 重定向后识别京东商品 resolved={resolved}")
        return resolved

    if _is_supported_product_host(urlparse(final_url).netloc):
        print(
            f"[ProductInfoService] 使用重定向 URL resolved={final_url} "
            f"+{_elapsed_ms(started)}ms"
        )
        return final_url

    raise ValueError("链接未能解析为淘宝/天猫/京东商品详情页，请检查链接是否正确")


def _extract_json_ld_product(soup: BeautifulSoup) -> dict[str, Any]:
    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.string or script.get_text()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue

        candidates = data if isinstance(data, list) else [data]
        for item in candidates:
            if not isinstance(item, dict):
                continue
            item_type = str(item.get("@type", "")).lower()
            if "product" in item_type:
                return item
    return {}


def _html_to_plain_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "iframe"]):
        tag.decompose()

    chunks: list[str] = []
    json_ld = _extract_json_ld_product(soup)
    if json_ld:
        for key in ("name", "description", "brand"):
            value = json_ld.get(key)
            if isinstance(value, dict):
                value = value.get("name")
            if value:
                chunks.append(str(value))

    title = soup.find("title")
    if title:
        chunks.append(title.get_text(" ", strip=True))

    meta_desc = soup.find("meta", attrs={"name": "description"})
    if meta_desc and meta_desc.get("content"):
        chunks.append(str(meta_desc["content"]))

    body_text = soup.get_text(" ", strip=True)
    if body_text:
        chunks.append(body_text)

    merged = " ".join(chunks)
    merged = re.sub(r"\s+", " ", merged).strip()
    return merged[:12000]


async def fetch_product_page_text(url: str) -> str:
    """httpx 静态抓取商品页文本（Playwright 不可用时的回退）。"""
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=httpx.Timeout(20.0),
        headers=_DEFAULT_HEADERS,
    ) as client:
        response = await client.get(url)
        response.raise_for_status()
        return _html_to_plain_text(response.text)


def compose_product_context(
    *,
    url: str,
    page_text: str = "",
    vision_text: str = "",
    search_text: str = "",
    price: float | None = None,
    sales: int | None = None,
) -> str:
    """合并页面文本、图片识别与检索补充，供 LLM 提取。"""
    parts: list[str] = [f"商品链接：{url}"]
    if price is not None and price > 0:
        parts.append(f"页面价格：{price:g}")
    if sales is not None and sales > 0:
        parts.append(f"页面销量：{sales}")
    if page_text.strip():
        parts.append(f"页面文本：{page_text.strip()[:8000]}")
    if vision_text.strip():
        parts.append(f"图片识别补充：{vision_text.strip()[:3000]}")
    if search_text.strip():
        parts.append(f"检索补充：{search_text.strip()[:3000]}")
    return "\n".join(parts)


@dataclass
class ProductGatherResult:
    """商品上下文汇总结果（含爬虫原始数据）。"""

    context: str
    capture: ProductPageCapture | None = None
    page_text: str = ""
    vision_text: str = ""
    search_text: str = ""


@dataclass
class PreparedProduct:
    """已完成抓取与字段提取、待入库的商品数据。"""

    normalized_url: str
    fields: dict[str, Any]
    gather: ProductGatherResult
    search_text: str


_PREVIEW_CACHE_TTL_SEC = 600
_preview_cache: dict[str, tuple[float, PreparedProduct]] = {}


def _prune_preview_cache() -> None:
    now = time.time()
    expired = [
        token
        for token, (created_at, _) in _preview_cache.items()
        if now - created_at > _PREVIEW_CACHE_TTL_SEC
    ]
    for token in expired:
        del _preview_cache[token]


def _cache_prepared_product(prepared: PreparedProduct) -> str:
    _prune_preview_cache()
    token = secrets.token_urlsafe(24)
    _preview_cache[token] = (time.time(), prepared)
    return token


def _pop_prepared_product(token: str) -> PreparedProduct:
    _prune_preview_cache()
    entry = _preview_cache.pop((token or "").strip(), None)
    if not entry:
        raise ValueError("识别结果已过期或无效，请重新识别商品链接")
    created_at, prepared = entry
    if time.time() - created_at > _PREVIEW_CACHE_TTL_SEC:
        raise ValueError("识别结果已过期，请重新识别商品链接")
    return prepared


def _truncate_scrape_text(text: str, max_chars: int = SCRAPE_TEXT_MAX_CHARS) -> str:
    cleaned = (text or "").strip()
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[:max_chars]


def _join_scrape_images(capture: ProductPageCapture | None) -> str:
    if not capture:
        return ""
    images: list[str] = []
    if capture.head_image_url:
        images.append(capture.head_image_url)
    for url in capture.detail_image_urls or []:
        if url and url not in images:
            images.append(url)
    return DETAIL_IMAGE_SEPARATOR.join(images)


def build_scrape_payload(
    url: str,
    gather: ProductGatherResult,
) -> dict[str, Any]:
    """组装写入 CSV 的爬虫原始字段。"""
    capture = gather.capture
    return {
        "scrape_title": capture.title if capture else "",
        "scrape_platform": capture.platform if capture else "",
        "scrape_source": capture.source if capture else "",
        "scrape_final_url": capture.final_url if capture else url,
        "scrape_price": capture.price if capture else None,
        "scrape_sales": capture.sales if capture else None,
        "scrape_shop": capture.shop if capture else "",
        "scrape_price_text": capture.price_text if capture else "",
        "scrape_visible_text": _truncate_scrape_text(gather.page_text),
        "scrape_vision_text": _truncate_scrape_text(gather.vision_text),
        "scrape_search_text": _truncate_scrape_text(gather.search_text),
        "scrape_detail_images": _join_scrape_images(capture),
        "scrape_screenshot_url": capture.screenshot_url if capture else "",
        "comments_list": capture.comments_list if capture else [],
        "scrape_comments_status": capture.comments_status if capture else "",
    }


async def _search_product_context(url: str) -> str:
    """页面抓取失败时，用检索结果补充商品上下文。"""
    started = time.perf_counter()
    print(f"[ProductInfoService] 开始检索回退 url={url}")
    taobao_id = _extract_taobao_item_id(url)
    jd_id = _extract_jd_item_id(url)
    snippet = await asyncio.to_thread(
        search_product_context_snippets,
        url=url,
        taobao_item_id=taobao_id,
        jd_item_id=jd_id,
    )
    if snippet.strip():
        print(
            f"[ProductInfoService] 检索回退命中 snippet_len={len(snippet.strip())} "
            f"+{_elapsed_ms(started)}ms"
        )
        return snippet.strip()

    parsed = urlparse(url)
    is_jd = "jd" in parsed.netloc.lower()
    fallback_queries: list[str] = []
    if taobao_id:
        fallback_queries.append(f"淘宝 商品 id={taobao_id}")
    if jd_id:
        fallback_queries.append(f"京东 商品 {jd_id}")
    fallback_queries.append(url)

    site = "jd.com" if is_jd else "taobao.com"
    for query in fallback_queries:
        print(f"[ProductInfoService] DuckDuckGo 回退 query={query!r}")
        result = await search_duckduckgo_langchain_async(query, site=site)
        if result and len(result.strip()) >= 40:
            print(
                f"[ProductInfoService] DuckDuckGo 回退命中 result_len={len(result.strip())} "
                f"+{_elapsed_ms(started)}ms"
            )
            return result.strip()
    print(f"[ProductInfoService] 检索回退无结果 +{_elapsed_ms(started)}ms")
    return ""


async def _enrich_jd_price_sales_from_search(
    capture: ProductPageCapture,
    url: str,
) -> str:
    """京东价格/销量缺失时，用检索摘要补充并写回 capture。"""
    jd_id = _extract_jd_item_id(url) or _extract_jd_item_id(capture.final_url)
    if not jd_id:
        return ""

    need_price = capture.price is None or capture.price <= 0
    need_sales = capture.sales is None or capture.sales <= 0
    if not need_price and not need_sales:
        return ""

    snippet = search_jd_product_price_snippets(
        title=capture.title or "",
        jd_item_id=jd_id,
    )
    if not snippet.strip():
        return ""

    if need_price:
        parsed_price = _parse_price_from_visible_text(snippet)
        if parsed_price is not None and parsed_price > 0:
            capture.price = parsed_price
            print(
                f"[ProductInfoService] 检索回退命中京东价格 price={parsed_price} "
                f"sku={jd_id}"
            )
    if need_sales:
        parsed_sales = _parse_sales_from_visible_text(snippet)
        if parsed_sales is not None and parsed_sales > 0:
            capture.sales = parsed_sales
            print(
                f"[ProductInfoService] 检索回退命中京东销量 sales={parsed_sales} "
                f"sku={jd_id}"
            )
    return snippet.strip()


def _parse_price_sales_from_vision_text(vision_text: str) -> tuple[float | None, int | None]:
    price = None
    sales = None
    for line in (vision_text or "").splitlines():
        cleaned = line.strip()
        if cleaned.startswith("价格：") or cleaned.startswith("价格:"):
            match = re.search(r"(\d+(?:\.\d+)?)", cleaned)
            if match:
                try:
                    price = float(match.group(1))
                except ValueError:
                    price = None
        if cleaned.startswith("销量：") or cleaned.startswith("销量:"):
            match = re.search(r"(\d+)", cleaned.replace(",", ""))
            if match:
                try:
                    sales = int(match.group(1))
                except ValueError:
                    sales = None
    if price is None:
        price = _parse_price_from_visible_text(vision_text)
    if sales is None:
        sales = _parse_sales_from_visible_text(vision_text)
    return price, sales


async def extract_vision_product_context(url: str, capture: ProductPageCapture) -> str:
    """用多模态大模型识别截图与详情图中的商品信息。"""
    started = time.perf_counter()
    image_payload = await build_vision_image_payload(capture)
    if not image_payload:
        print("[ProductInfoService] 无可用图片，跳过视觉识别")
        return ""

    model_name = settings.PRODUCT_VISION_MODEL or settings.BASE_MODEL
    print(
        f"[ProductInfoService] 开始视觉识别 model={model_name} "
        f"images={len(image_payload)}"
    )
    client = AsyncOpenAI(api_key=settings.API_KEY, base_url=settings.MODEL_BASE_URL)

    content: list[dict[str, Any]] = [
        {"type": "text", "text": _VISION_PROMPT.format(url=url)},
    ]
    for image_data in image_payload:
        content.append({"type": "image_url", "image_url": {"url": image_data}})

    try:
        llm_started = time.perf_counter()
        response = await client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": content}],
            temperature=0.1,
            max_tokens=600,
        )
        print(
            f"[ProductInfoService] 视觉识别 LLM 完成 +{_elapsed_ms(llm_started)}ms "
            f"total={_elapsed_ms(started)}ms"
        )
    except Exception as exc:
        print(f"[ProductInfoService] 图片识别失败: {exc}")
        return ""

    message = response.choices[0].message.content if response.choices else ""
    vision_text = (message or "").strip()
    print(f"[ProductInfoService] 视觉识别结果 vision_len={len(vision_text)}")
    return vision_text


def _is_usable_page_text(text: str, *, product_title: str = "") -> bool:
    return is_usable_product_page_text(
        text,
        product_title=product_title,
        min_chars=_MIN_PAGE_TEXT_CHARS,
    )


_LOW_QUALITY_PRODUCT_NAMES = frozenset(
    {"未知商品", "未知", "商品", "未命名商品", "未识别商品"}
)


def _resolve_product_name(parsed_name: str, capture: ProductPageCapture | None) -> str:
    candidate = (parsed_name or "").strip()
    if candidate and candidate not in _LOW_QUALITY_PRODUCT_NAMES:
        return candidate

    fallback = (capture.title or "").strip() if capture else ""
    if fallback and fallback not in _LOW_QUALITY_PRODUCT_NAMES:
        if capture and capture.platform == "jd" and is_jd_blocked_page("", title=fallback):
            return candidate
        print(
            f"[ProductInfoService] 使用页面标题兜底商品名 parsed={candidate!r} "
            f"fallback={fallback[:80]!r}"
        )
        return fallback
    return candidate


def _validate_extracted_product_fields(fields: dict[str, Any]) -> None:
    name = str(fields.get("name", "")).strip()
    description = str(fields.get("description", "")).strip()

    if not name or name in _LOW_QUALITY_PRODUCT_NAMES:
        raise ValueError("未能识别有效商品名称，请确认链接可访问且已安装 Playwright 渲染抓取")

    if any(
        phrase in description
        for phrase in ("无法从页面", "无法提取", "未能从页面", "无有效商品信息")
    ):
        raise ValueError("商品详情解析失败，页面可能需登录或为反爬页，请稍后重试")


async def gather_product_context(url: str) -> ProductGatherResult:
    """汇总 Playwright 文本、视觉识别与检索补充。"""
    started = time.perf_counter()
    print(f"[ProductInfoService] 开始汇总商品上下文 url={url}")
    page_text = ""
    vision_text = ""
    search_text = ""
    capture: ProductPageCapture | None = None

    scrape_started = time.perf_counter()
    capture = await capture_product_page(url)
    print(f"[ProductInfoService] Playwright 阶段完成 +{_elapsed_ms(scrape_started)}ms")
    if capture is None and "jd" in urlparse(url).netloc.lower():
        raise ValueError(
            "京东页面访问被限流或需登录，请在 backend/.env 配置 PRODUCT_JD_COOKIE"
            "（浏览器 jd.com 的 Cookie 字符串）后重试"
        )
    if capture:
        candidate_text = (capture.visible_text or "").strip()
        if _is_usable_page_text(candidate_text, product_title=capture.title or ""):
            page_text = candidate_text
            print(
                f"[ProductInfoService] 采用页面文本 page_len={len(page_text)} "
                f"title={capture.title[:60]!r}"
            )
        else:
            print(
                f"[ProductInfoService] 页面文本未采用 page_len={len(candidate_text)} "
                f"title={capture.title[:60]!r}"
            )
        if capture.screenshot_url or capture.detail_image_urls:
            vision_started = time.perf_counter()
            vision_text = await extract_vision_product_context(url, capture)
            print(
                f"[ProductInfoService] 视觉识别阶段完成 vision_len={len(vision_text)} "
                f"+{_elapsed_ms(vision_started)}ms"
            )
            if capture.platform == "jd":
                vision_price, vision_sales = _parse_price_sales_from_vision_text(vision_text)
                if (capture.price is None or capture.price <= 0) and vision_price:
                    capture.price = vision_price
                    print(f"[ProductInfoService] 视觉识别命中价格 price={vision_price}")
                if (capture.sales is None or capture.sales <= 0) and vision_sales:
                    capture.sales = vision_sales
                    print(f"[ProductInfoService] 视觉识别命中销量 sales={vision_sales}")
    elif settings.PRODUCT_SCRAPER_USE_PLAYWRIGHT and not is_playwright_available():
        print(
            f"[ProductInfoService] Playwright 未安装，商品页将仅能使用检索回退。"
            f" 建议执行: {playwright_setup_hint()}"
        )

    price_search_text = ""
    if capture and capture.platform == "jd":
        price_search_text = await _enrich_jd_price_sales_from_search(capture, url)

    if not page_text and not vision_text:
        search_text = await _search_product_context(url)
    elif price_search_text:
        search_text = price_search_text

    context = compose_product_context(
        url=url,
        page_text=page_text,
        vision_text=vision_text,
        search_text=search_text,
        price=capture.price if capture else None,
        sales=capture.sales if capture else None,
    )

    usable_chars = len(
        re.sub(
            r"\s+",
            "",
            f"{page_text}{vision_text}{search_text}",
        )
    )
    print(
        f"[ProductInfoService] 上下文汇总完成 page_len={len(page_text)} "
        f"vision_len={len(vision_text)} search_len={len(search_text)} "
        f"price={capture.price if capture else None} "
        f"sales={capture.sales if capture else None} "
        f"usable_chars={usable_chars} total={_elapsed_ms(started)}ms"
    )
    if usable_chars < 20:
        raise ValueError(
            "未能获取商品信息。请确认链接有效；若页面需登录，可稍后重试或更换链接。"
        )

    return ProductGatherResult(
        context=context,
        capture=capture,
        page_text=page_text,
        vision_text=vision_text,
        search_text=search_text,
    )


def _parse_llm_json(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("模型未返回有效 JSON")

    return json.loads(text[start : end + 1])


async def extract_product_fields(
    url: str,
    page_text: str,
    *,
    capture: ProductPageCapture | None = None,
    vision_text: str = "",
) -> dict[str, Any]:
    """用 LLM 从页面上下文提取商品字段。"""
    if not page_text.strip():
        raise ValueError("未能从商品页获取有效文本，请检查链接是否可访问")

    started = time.perf_counter()
    print(
        f"[ProductInfoService] 开始 LLM 字段提取 context_len={len(page_text)} url={url}"
    )
    result = await llm_factory.run_chain_with_dynamic_tokens(
        prompt_template=_EXTRACT_PROMPT,
        chain_input={"url": url, "page_text": page_text[:8000]},
        temperature=0.1,
        agent_name="ProductInfoService",
    )
    print(f"[ProductInfoService] LLM 字段提取完成 +{_elapsed_ms(started)}ms")
    raw_text = result.content if hasattr(result, "content") else str(result)
    parsed = _parse_llm_json(raw_text)

    try:
        price = float(parsed.get("price", 0) or 0)
    except (TypeError, ValueError):
        price = 0.0

    try:
        sales = int(parsed.get("sales", 0) or 0)
    except (TypeError, ValueError):
        sales = 0

    if capture:
        if price <= 0 and capture.price is not None and capture.price > 0:
            price = capture.price
        if sales <= 0 and capture.sales is not None and capture.sales > 0:
            sales = capture.sales

    fields = {
        "name": _resolve_product_name(str(parsed.get("name", "")).strip(), capture),
        "category": str(parsed.get("category", "")).strip() or "未分类",
        "description": str(parsed.get("description", "")).strip(),
        "shop_name": str(parsed.get("shop_name", "")).strip() or "未知店铺",
        "price": price,
        "sales": sales,
    }
    if len(fields["description"]) < 80 and vision_text.strip():
        fields["description"] = vision_text.strip()[:500]
    elif not fields["description"] and capture and (capture.title or "").strip():
        fields["description"] = capture.title.strip()[:500]
    _validate_extracted_product_fields(fields)
    print(
        f"[ProductInfoService] 字段解析成功 name={fields['name']!r} "
        f"category={fields['category']!r} description_len={len(fields['description'])} "
        f"price={fields['price']} sales={fields['sales']}"
    )
    return fields


def _normalize_optional_url(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    return text


def _preview_cover_image(prepared: PreparedProduct) -> str | None:
    capture = prepared.gather.capture
    if not capture:
        return None
    if capture.head_image_url:
        return capture.head_image_url
    if capture.detail_image_urls:
        return capture.detail_image_urls[0]
    return None


def _preview_comments(prepared: PreparedProduct) -> list[ProductComment]:
    capture = prepared.gather.capture
    if not capture or not capture.comments_list:
        return []

    comments: list[ProductComment] = []
    for item in capture.comments_list[:_PREVIEW_COMMENTS_LIMIT]:
        if not isinstance(item, dict):
            continue
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        comments.append(
            ProductComment(
                content=content,
                nickname=str(item.get("nickname") or "").strip(),
                score=str(item.get("score") or "").strip(),
                creation_time=str(item.get("creation_time") or "").strip(),
            )
        )
    return comments


def prepared_product_to_item(prepared: PreparedProduct) -> ProductItem:
    return ProductItem(
        id="preview",
        name=prepared.fields["name"],
        category=prepared.fields["category"],
        price=float(prepared.fields.get("price", 0) or 0),
        description=prepared.fields.get("description", ""),
        sales=int(prepared.fields.get("sales", 0) or 0),
        shop_name=prepared.fields.get("shop_name", ""),
        url=prepared.normalized_url,
        cover_image=_preview_cover_image(prepared),
        comments=_preview_comments(prepared),
    )


def _cover_image_from_scrape_record(scrape: dict[str, Any] | None) -> str | None:
    if not scrape:
        return None
    raw = str(scrape.get("scrape_detail_images") or "").strip()
    if raw:
        first = raw.split(DETAIL_IMAGE_SEPARATOR)[0].strip()
        if first:
            return first
    screenshot = str(scrape.get("scrape_screenshot_url") or "").strip()
    return screenshot or None


def _comments_from_scrape_record(scrape: dict[str, Any] | None) -> list[ProductComment]:
    if not scrape:
        return []
    raw = scrape.get("comments_list")
    if not raw:
        return []
    try:
        parsed = json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []

    comments: list[ProductComment] = []
    for item in parsed[:_PREVIEW_COMMENTS_LIMIT]:
        if not isinstance(item, dict):
            continue
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        comments.append(
            ProductComment(
                content=content,
                nickname=str(item.get("nickname") or "").strip(),
                score=str(item.get("score") or "").strip(),
                creation_time=str(item.get("creation_time") or "").strip(),
            )
        )
    return comments


def product_record_to_item(
    record: dict,
    *,
    scrape: dict[str, Any] | None = None,
) -> ProductItem:
    return ProductItem(
        id=str(record["id"]),
        name=record["name"],
        category=record["category"],
        price=float(record.get("price", 0) or 0),
        description=record.get("description", ""),
        sales=int(record.get("sales", 0) or 0),
        shop_name=record.get("shop_name", ""),
        url=_normalize_optional_url(record.get("url")),
        cover_image=_cover_image_from_scrape_record(scrape),
        comments=_comments_from_scrape_record(scrape),
    )


class ProductInfoService:
    """选品池商品信息服务。"""

    def __init__(self, rag_agent: ProductRagAgent):
        self.rag_agent = rag_agent

    def list_products(self) -> ProductListResponse:
        records = sorted(
            self.rag_agent.products_db.get_all_products(),
            key=lambda record: int(record["id"]),
            reverse=True,
        )
        items = [product_record_to_item(record) for record in records]
        return ProductListResponse(items=items, total=len(items))

    def get_product(self, product_id: str) -> ProductItem | None:
        record = self.rag_agent.products_db.get_product_by_id(product_id)
        if not record:
            return None
        scrape = self.rag_agent.scrape_db.get_by_product_id(product_id)
        return product_record_to_item(record, scrape=scrape)

    async def _prepare_product_from_url(self, url: str) -> PreparedProduct:
        normalized_url = await resolve_product_url(url)
        gather = await gather_product_context(normalized_url)
        fields = await extract_product_fields(
            normalized_url,
            gather.context,
            capture=gather.capture,
            vision_text=gather.vision_text,
        )

        search_text = ProductDatabase.build_search_text(
            fields["name"],
            fields["category"],
            fields["description"],
            fields["shop_name"],
            max_tokens=SEARCH_TEXT_MAX_TOKENS,
        )
        if token_counter.count_tokens(search_text) > SEARCH_TEXT_MAX_TOKENS:
            raise ValueError("检索文本超出 512 token 上限")

        return PreparedProduct(
            normalized_url=normalized_url,
            fields=fields,
            gather=gather,
            search_text=search_text,
        )

    async def _persist_prepared_product(
        self,
        prepared: PreparedProduct,
        *,
        log_label: str,
    ) -> ProductInfoCreateResponse:
        started = time.perf_counter()
        persisted_url = _preview_cover_image(prepared) or prepared.normalized_url
        record = self.rag_agent.products_db.add_product(
            {
                **prepared.fields,
                "url": persisted_url,
                "search_text": prepared.search_text,
            }
        )
        scrape_record = self.rag_agent.scrape_db.add_scrape_record(
            product_id=record["id"],
            url=prepared.normalized_url,
            product_fields=prepared.fields,
            scrape_payload=build_scrape_payload(prepared.normalized_url, prepared.gather),
            search_text=prepared.search_text,
        )
        await self.rag_agent.ensure_index_ready()
        await asyncio.to_thread(self.rag_agent.add_product_to_index, record)

        scrape = self.rag_agent.scrape_db.get_by_product_id(record["id"])
        item = product_record_to_item(record, scrape=scrape)
        print(
            f"[ProductInfoService] {log_label} 完成 product_id={item.id} "
            f"name={item.name!r} products_csv={self.rag_agent.products_db.data_path} "
            f"scrape_csv={self.rag_agent.scrape_db.data_path} scrape_id={scrape_record['id']} "
            f"total={_elapsed_ms(started)}ms"
        )
        return ProductInfoCreateResponse(product=item)

    async def preview_from_url(self, url: str) -> ProductInfoPreviewResponse:
        started = time.perf_counter()
        print(f"[ProductInfoService] preview_from_url 开始 url={url}")
        prepared = await self._prepare_product_from_url(url)
        preview_token = _cache_prepared_product(prepared)
        item = prepared_product_to_item(prepared)
        print(
            f"[ProductInfoService] preview_from_url 完成 name={item.name!r} "
            f"category={item.category!r} description_len={len(item.description)} "
            f"cover_image={'yes' if item.cover_image else 'no'} comments={len(item.comments)} "
            f"token={preview_token[:8]}... total={_elapsed_ms(started)}ms"
        )
        return ProductInfoPreviewResponse(preview_token=preview_token, product=item)

    async def confirm_preview(self, preview_token: str) -> ProductInfoCreateResponse:
        print(f"[ProductInfoService] confirm_preview 开始 token={preview_token[:8]}...")
        prepared = _pop_prepared_product(preview_token)
        return await self._persist_prepared_product(prepared, log_label="confirm_preview")

    async def create_from_url(self, url: str) -> ProductInfoCreateResponse:
        started = time.perf_counter()
        print(f"[ProductInfoService] create_from_url 开始 url={url}")
        prepared = await self._prepare_product_from_url(url)
        response = await self._persist_prepared_product(prepared, log_label="create_from_url")
        print(f"[ProductInfoService] create_from_url 总耗时 total={_elapsed_ms(started)}ms")
        return response

    def delete_product(self, product_id: str) -> bool:
        removed = self.rag_agent.products_db.delete_product(product_id)
        if not removed:
            return False
        self.rag_agent.scrape_db.delete_by_product_id(product_id)
        self.rag_agent.remove_product_from_index(product_id)
        return True
