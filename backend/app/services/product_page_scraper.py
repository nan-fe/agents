"""Playwright 商品详情页抓取：等待渲染后提取可见文本与详情图。"""

from __future__ import annotations

import base64
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

import httpx

from app.config import settings

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9",
}

_MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)

_TITLE_SELECTORS = (
    ".tb-main-title",
    "[class*='MainTitle']",
    "[class*='ItemTitle']",
    "#J_Title",
    ".sku-name",
    ".itemInfo-wrap h1",
    "h1",
)

_DETAIL_IMAGE_SELECTORS = (
    "#description img",
    "#J_DivItemDesc img",
    ".detail-content img",
    "[class*='descV8'] img",
    "[class*='detail'] img",
    "#detail img",
    ".item-detail img",
)

_HEAD_IMAGE_SELECTORS: dict[str, tuple[str, ...]] = {
    "jd": (
        "#spec-img img",
        ".image-zoom-view img",
        "#preview img",
        "[class*='main-img'] img",
        ".product-intro img",
        "#main-image img",
    ),
    "taobao": (
        "#J_ImgBooth img",
        "#J_UlThumb li img",
        ".tb-thumb img",
        "[class*='PicGallery'] img",
        "[class*='mainPic'] img",
    ),
    "tmall": (
        "#J_ImgBooth img",
        "#J_UlThumb li img",
        ".tb-thumb img",
        "[class*='PicGallery'] img",
        "[class*='mainPic'] img",
    ),
}

_BLOCKED_TEXT_MARKERS = (
    "请登录",
    "验证码",
    "访问受限",
    "slide to verify",
)

# 仅在没有商品标题时出现，才视为京东首页/反爬页（商品详情页页脚也会带品牌 slogan）
_JD_HOMEPAGE_MARKERS = (
    "京东(JD.COM)-正品低价、品质保障、配送及时、轻松购物",
    "京东JD.COM-专业的综合网上购物商城",
)


def is_usable_product_page_text(
    text: str,
    *,
    product_title: str = "",
    min_chars: int = 80,
) -> bool:
    """判断 Playwright 抓取的页面文本是否可用于商品解析。"""
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    title = (product_title or "").strip()

    if title and len(title) >= 4 and not any(m in title for m in _BLOCKED_TEXT_MARKERS):
        return True

    if len(cleaned) < min_chars:
        return False
    if any(marker in cleaned for marker in _BLOCKED_TEXT_MARKERS):
        return False
    if any(marker in cleaned for marker in _JD_HOMEPAGE_MARKERS):
        return False
    return True


def _is_usable_visible_text(text: str, min_chars: int = 80, *, product_title: str = "") -> bool:
    return is_usable_product_page_text(
        text,
        product_title=product_title,
        min_chars=min_chars,
    )


def is_playwright_available() -> bool:
    try:
        import playwright  # noqa: F401
        return True
    except ImportError:
        return False


def playwright_setup_hint() -> str:
    return "python3 -m pip install playwright && python3 -m playwright install chromium"


def _elapsed_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


_JD_ITEM_ID_RE = re.compile(r"/(\d+)\.html")
_TAOBAO_ITEM_ID_RE = re.compile(r"[?&]id=(\d+)")
_SCREENSHOT_URL_PREFIX = "/product-screenshots"


def get_product_screenshot_dir() -> Path:
    """商品页截图本地目录（由 FastAPI 静态路由对外提供）。"""
    directory = (
        Path(__file__).resolve().parents[1]
        / "agents"
        / "product_rag_system"
        / "data"
        / "screenshots"
    )
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def screenshot_local_path(screenshot_url: str) -> Path | None:
    """将 `/product-screenshots/xxx.jpg` 转为本地文件路径。"""
    prefix = f"{_SCREENSHOT_URL_PREFIX}/"
    if not (screenshot_url or "").startswith(prefix):
        return None
    filename = screenshot_url[len(prefix) :].strip()
    if not filename or "/" in filename or ".." in filename:
        return None
    return get_product_screenshot_dir() / filename


def _extract_item_key(url: str) -> str:
    jd_id = _extract_jd_item_id(url)
    if jd_id:
        return jd_id
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    if "id" in query and query["id"]:
        return query["id"][0]
    match = _TAOBAO_ITEM_ID_RE.search(url)
    if match:
        return match.group(1)
    slug = re.sub(r"[^\w.-]+", "_", parsed.path.strip("/"))[:40]
    return slug or str(int(time.time()))


def save_product_screenshot(image_bytes: bytes, *, platform: str, url: str) -> str:
    """保存截图到本地并返回可访问 URL（不含 base64）。"""
    item_key = re.sub(r"[^\w.-]+", "_", _extract_item_key(url))
    filename = f"{platform}_{item_key}.jpg"
    path = get_product_screenshot_dir() / filename
    path.write_bytes(image_bytes)
    screenshot_url = f"{_SCREENSHOT_URL_PREFIX}/{filename}"
    print(f"[ProductPageScraper] 截图已保存 url={screenshot_url} path={path}")
    return screenshot_url


def _extract_jd_item_id(url: str) -> str | None:
    match = _JD_ITEM_ID_RE.search(url)
    return match.group(1) if match else None


def _parse_numeric_price(raw: str) -> float | None:
    text = (raw or "").strip().replace(",", "").replace("，", "")
    if not text or "?" in text:
        return None
    match = re.search(r"(\d+(?:\.\d+)?)", text)
    if not match:
        return None
    try:
        value = float(match.group(1))
    except ValueError:
        return None
    return value if value > 0 else None


def _parse_price_from_visible_text(text: str) -> float | None:
    for pattern in (
        r"页面价格[：:\s]*([\d,.]+)",
        r"京东价[：:\s]*[¥￥]?\s*([\d,.]+)",
        r"[¥￥]\s*([\d,.]+)",
    ):
        match = re.search(pattern, text or "")
        if match:
            price = _parse_numeric_price(match.group(1))
            if price is not None:
                return price
    return None


def _parse_sales_count(raw: str) -> int | None:
    text = (raw or "").strip().replace(",", "").replace("，", "")
    if not text:
        return None
    match = re.search(r"(\d+(?:\.\d+)?)\s*万", text)
    if match:
        try:
            return int(float(match.group(1)) * 10000)
        except ValueError:
            return None
    match = re.search(r"(\d+)", text)
    if not match:
        return None
    try:
        value = int(match.group(1))
    except ValueError:
        return None
    return value if value > 0 else None


def _parse_sales_from_visible_text(text: str) -> int | None:
    for pattern in (
        r"页面销量[：:\s]*(\d+(?:\.\d+)?万?\+?)",
        r"(\d+(?:\.\d+)?万?\+?)\s*条评价",
        r"累计评价[：:\s]*(\d+(?:\.\d+)?万?\+?)",
        r"销量[：:\s]*(\d+(?:\.\d+)?万?\+?)",
    ):
        match = re.search(pattern, text or "")
        if match:
            sales = _parse_sales_count(match.group(1))
            if sales is not None:
                return sales
    return None


_JD_COMMENTS_LIMIT = 10
_JD_COMMENT_API_URLS = (
    # 2017 年 fredfeng0326/Scraping 项目使用的端点（部分环境仍可用）
    "https://sclub.jd.com/comment/productPageComments.action",
    "https://club.jd.com/comment/productPageComments.action",
)
_JD_COMMENT_RETRY_COUNT = 5
_JD_COMMENT_RETRY_SLEEP_SEC = 3.0
_JD_API_BUSY_MARKERS = ("系统繁忙", "绯荤粺绻佸繖")


def _decode_jd_api_body(raw: bytes) -> str:
    """京东部分接口返回 GBK；Playwright 有时已正确解码，这里做兜底。"""
    if not raw:
        return ""
    for encoding in ("utf-8", "gbk", "gb18030"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _normalize_jd_comment_items(raw_comments: Any, limit: int = _JD_COMMENTS_LIMIT) -> list[dict[str, str]]:
    """将京东评论接口返回标准化为 comments_list。"""
    if not isinstance(raw_comments, list):
        return []

    comments_list: list[dict[str, str]] = []
    for item in raw_comments:
        if not isinstance(item, dict):
            continue
        content = re.sub(r"\s+", " ", str(item.get("content") or "")).strip()
        if not content:
            continue
        comments_list.append(
            {
                "content": content,
                "nickname": str(item.get("nickname") or "").strip(),
                "score": str(item.get("score") or "").strip(),
                "creation_time": str(
                    item.get("creationTime") or item.get("referenceTime") or ""
                ).strip(),
            }
        )
        if len(comments_list) >= limit:
            break
    return comments_list


def _parse_jd_comments_response(
    body: str,
    limit: int = _JD_COMMENTS_LIMIT,
) -> tuple[list[dict[str, str]], str]:
    """解析评论接口响应，返回 (comments_list, status)。"""
    text = (body or "").strip()
    if not text:
        return [], "empty_response"
    if any(marker in text for marker in _JD_API_BUSY_MARKERS):
        return [], "api_blocked"
    json_match = re.search(r"\{.*\}", text, re.DOTALL)
    if not json_match:
        return [], "invalid_response"
    try:
        data = json.loads(json_match.group(0))
    except json.JSONDecodeError:
        return [], "invalid_json"
    comments_list = _normalize_jd_comment_items(data.get("comments") or [], limit=limit)
    if comments_list:
        return comments_list, "ok"
    return [], "no_comments"


async def _scrape_jd_comments_from_dom(page, limit: int = _JD_COMMENTS_LIMIT) -> list[dict[str, str]]:
    """从已渲染的评价区 DOM 提取评论（接口不可用时的回退）。"""
    try:
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(2000)
        raw_items = await page.evaluate(
            """(limit) => {
                const selectors = [
                    '.comment-item .comment-con',
                    '.reviews-items .review-item .review-content',
                    '[class*="comment"] [class*="content"]',
                    '#comment .con',
                ];
                const texts = [];
                for (const selector of selectors) {
                    document.querySelectorAll(selector).forEach((node) => {
                        const content = (node.textContent || '').replace(/\\s+/g, ' ').trim();
                        if (content.length >= 8) texts.push(content);
                    });
                    if (texts.length >= limit) break;
                }
                return texts.slice(0, limit);
            }""",
            limit,
        )
    except Exception:
        return []

    comments_list: list[dict[str, str]] = []
    for content in raw_items or []:
        text = str(content).strip()
        if not text:
            continue
        comments_list.append(
            {
                "content": text,
                "nickname": "",
                "score": "",
                "creation_time": "",
            }
        )
    return comments_list


async def _request_jd_comment_api(
    page,
    item_id: str,
    *,
    api_url: str,
    limit: int,
    referer: str,
) -> tuple[str, int]:
    """请求京东评论 JSON/JSONP 接口，返回 (body, http_status)。"""
    resp = await page.request.get(
        api_url,
        params={
            "productId": item_id,
            "score": "0",
            "sortType": "5",
            "page": "0",
            "pageSize": str(limit),
            "isShadowSku": "0",
            "fold": "1",
        },
        headers={"Referer": referer},
        timeout=12_000,
    )
    raw = await resp.body()
    body = await resp.text()
    if not body.strip():
        body = _decode_jd_api_body(raw)
    return body, resp.status


async def _fetch_jd_comments_via_browser_fetch(
    page,
    item_id: str,
    limit: int,
) -> tuple[list[dict[str, str]], str]:
    """在商品页上下文中 fetch 评论接口（携带页面 Cookie）。"""
    referer = f"https://item.jd.com/{item_id}.html"
    try:
        body = await page.evaluate(
            """async ({ itemId, limit, referer }) => {
                const params = new URLSearchParams({
                    productId: itemId,
                    score: '0',
                    sortType: '5',
                    page: '0',
                    pageSize: String(limit),
                    isShadowSku: '0',
                    fold: '1',
                });
                const url = `https://club.jd.com/comment/productPageComments.action?${params}`;
                const resp = await fetch(url, {
                    credentials: 'include',
                    headers: { Referer: referer },
                });
                return await resp.text();
            }""",
            {"itemId": item_id, "limit": limit, "referer": referer},
        )
    except Exception as exc:
        print(
            f"[ProductPageScraper] 京东评论浏览器 fetch 失败 sku={item_id} "
            f"{type(exc).__name__}: {exc!r}"
        )
        return [], "error"
    return _parse_jd_comments_response(str(body or ""), limit=limit)


async def _fetch_jd_comments_via_page(
    page,
    item_id: str,
    limit: int = _JD_COMMENTS_LIMIT,
) -> tuple[list[dict[str, str]], str]:
    """抓取京东商品具体评论（默认 10 条）。

    参考 fredfeng0326/Scraping：sclub.jd.com + GBK + 重试；并回退 club.jd.com / DOM。
    """
    referer = f"https://item.jd.com/{item_id}.html"
    last_status = "empty_response"
    try:
        for attempt in range(_JD_COMMENT_RETRY_COUNT + 1):
            for api_url in _JD_COMMENT_API_URLS:
                body, http_status = await _request_jd_comment_api(
                    page,
                    item_id,
                    api_url=api_url,
                    limit=limit,
                    referer=referer,
                )
                host = urlparse(api_url).netloc
                if not http_status or http_status >= 400:
                    print(
                        f"[ProductPageScraper] 京东评论接口 HTTP {http_status} "
                        f"host={host} sku={item_id} body={body[:160]!r}"
                    )
                    last_status = f"http_{http_status}"
                    continue

                comments_list, status = _parse_jd_comments_response(body, limit=limit)
                if status == "ok":
                    print(
                        f"[ProductPageScraper] 京东评论抓取 count={len(comments_list)} "
                        f"host={host} sku={item_id}"
                    )
                    return comments_list, status
                last_status = status
                if status != "api_blocked":
                    print(
                        f"[ProductPageScraper] 京东评论接口无数据 host={host} "
                        f"sku={item_id} status={status} body={body[:160]!r}"
                    )

            if attempt < _JD_COMMENT_RETRY_COUNT:
                print(
                    f"[ProductPageScraper] 京东评论接口被限流 sku={item_id}，"
                    f" 重试 {attempt + 1}/{_JD_COMMENT_RETRY_COUNT}"
                )
                await page.wait_for_timeout(int(_JD_COMMENT_RETRY_SLEEP_SEC * 1000))

        comments_list, status = await _fetch_jd_comments_via_browser_fetch(
            page, item_id, limit
        )
        if status == "ok" and comments_list:
            print(
                f"[ProductPageScraper] 京东评论浏览器 fetch 成功 count={len(comments_list)} "
                f"sku={item_id}"
            )
            return comments_list, "browser_fetch"

        print(
            f"[ProductPageScraper] 京东评论接口被限流(系统繁忙) sku={item_id}，"
            " 尝试从页面 DOM 回退"
        )
        dom_comments = await _scrape_jd_comments_from_dom(page, limit=limit)
        if dom_comments:
            print(
                f"[ProductPageScraper] 京东评论 DOM 回退成功 count={len(dom_comments)} "
                f"sku={item_id}"
            )
            return dom_comments, "dom_fallback"

        print(
            f"[ProductPageScraper] 京东评论抓取 count=0 "
            f"sku={item_id} status={last_status}"
        )
        return [], "api_blocked" if last_status == "api_blocked" else last_status
    except Exception as exc:
        print(
            f"[ProductPageScraper] 京东评论抓取失败 sku={item_id} "
            f"{type(exc).__name__}: {exc!r}"
        )
        return [], "error"


async def _fetch_jd_price_sales_via_page(page, item_id: str) -> tuple[float | None, int | None]:
    """在 Playwright 浏览器上下文中请求京东价格/评价接口（比 httpx 直连更稳定）。"""
    price: float | None = None
    sales: int | None = None
    referer = f"https://item.jd.com/{item_id}.html"
    headers = {"Referer": referer}

    try:
        price_resp = await page.request.get(
            "https://p.3.cn/prices/mgets",
            params={"skuIds": f"J_{item_id}", "type": "1"},
            headers=headers,
            timeout=12_000,
        )
        if price_resp.ok:
            payload = await price_resp.json()
            if isinstance(payload, list) and payload:
                price = _parse_numeric_price(
                    str(payload[0].get("p") or payload[0].get("op") or "")
                )
                print(f"[ProductPageScraper] 京东价格接口(浏览器) sku={item_id} price={price}")
        else:
            body = (await price_resp.text())[:160]
            print(
                f"[ProductPageScraper] 京东价格接口 HTTP {price_resp.status} "
                f"sku={item_id} body={body!r}"
            )
    except Exception as exc:
        print(
            f"[ProductPageScraper] 京东价格接口(浏览器)失败 sku={item_id} "
            f"{type(exc).__name__}: {exc!r}"
        )

    try:
        comment_resp = await page.request.get(
            "https://club.jd.com/comment/productCommentSummaries.action",
            params={"referenceIds": item_id},
            headers=headers,
            timeout=12_000,
        )
        if comment_resp.ok:
            body = (await comment_resp.text()).strip()
            json_match = re.search(r"\{.*\}", body, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
                comments = data.get("CommentsCount") or []
                if comments:
                    first = comments[0]
                    sales = _parse_sales_count(
                        str(first.get("CommentCountStr") or first.get("CommentCount") or "")
                    )
                    if sales is None and first.get("CommentCount") is not None:
                        try:
                            sales = int(first["CommentCount"])
                        except (TypeError, ValueError):
                            sales = None
                    print(f"[ProductPageScraper] 京东评价接口(浏览器) sku={item_id} sales={sales}")
            elif "系统繁忙" in body:
                print(f"[ProductPageScraper] 京东评价接口繁忙 sku={item_id}")
        else:
            body = (await comment_resp.text())[:160]
            print(
                f"[ProductPageScraper] 京东评价接口 HTTP {comment_resp.status} "
                f"sku={item_id} body={body!r}"
            )
    except Exception as exc:
        print(
            f"[ProductPageScraper] 京东评价接口(浏览器)失败 sku={item_id} "
            f"{type(exc).__name__}: {exc!r}"
        )

    return price, sales


async def _fetch_jd_price_sales(item_id: str) -> tuple[float | None, int | None]:
    """httpx 回退：浏览器上下文不可用时的兜底。"""
    price: float | None = None
    sales: int | None = None
    headers = {
        **_DEFAULT_HEADERS,
        "Referer": f"https://item.jd.com/{item_id}.html",
    }
    timeout = httpx.Timeout(12.0)

    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=timeout,
            headers=headers,
        ) as client:
            price_resp = await client.get(
                "https://p.3.cn/prices/mgets",
                params={"skuIds": f"J_{item_id}", "type": "1"},
            )
            if price_resp.status_code == 200:
                payload = price_resp.json()
                if isinstance(payload, list) and payload:
                    price = _parse_numeric_price(
                        str(payload[0].get("p") or payload[0].get("op") or "")
                    )
                    print(
                        f"[ProductPageScraper] 京东价格接口(httpx) sku={item_id} price={price}"
                    )

            comment_resp = await client.get(
                "https://club.jd.com/comment/productCommentSummaries.action",
                params={"referenceIds": item_id},
            )
            if comment_resp.status_code == 200:
                body = comment_resp.text.strip()
                json_match = re.search(r"\{.*\}", body, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group(0))
                    comments = data.get("CommentsCount") or []
                    if comments:
                        first = comments[0]
                        sales = _parse_sales_count(
                            str(first.get("CommentCountStr") or first.get("CommentCount") or "")
                        )
                        if sales is None and first.get("CommentCount") is not None:
                            try:
                                sales = int(first["CommentCount"])
                            except (TypeError, ValueError):
                                sales = None
                        print(
                            f"[ProductPageScraper] 京东评价接口(httpx) sku={item_id} sales={sales}"
                        )
    except Exception as exc:
        print(
            f"[ProductPageScraper] 京东价格/销量接口(httpx)失败 sku={item_id} "
            f"{type(exc).__name__}: {exc!r}"
        )

    return price, sales


async def _enrich_capture_price_sales(
    capture: ProductPageCapture,
    url: str,
    platform: str,
    *,
    page=None,
) -> None:
    price = _parse_price_from_visible_text(capture.visible_text)
    sales = _parse_sales_from_visible_text(capture.visible_text)

    if capture.price_text:
        dom_price = _parse_numeric_price(capture.price_text)
        if dom_price is not None:
            price = dom_price

    if platform == "jd":
        item_id = _extract_jd_item_id(url) or _extract_jd_item_id(capture.final_url)
        if item_id:
            if page is not None:
                api_price, api_sales = await _fetch_jd_price_sales_via_page(page, item_id)
            else:
                api_price, api_sales = await _fetch_jd_price_sales(item_id)
            if price is None:
                price = api_price
            if sales is None:
                sales = api_sales

    capture.price = price
    capture.sales = sales
    if price is not None or sales is not None:
        print(
            f"[ProductPageScraper] 结构化价格销量 price={price} sales={sales}"
        )
    elif platform == "jd":
        print(
            f"[ProductPageScraper] 未能获取京东价格/销量 sku="
            f"{_extract_jd_item_id(url) or _extract_jd_item_id(capture.final_url)} "
            f"price_text={capture.price_text[:40]!r}"
        )


async def _enrich_capture_comments(
    capture: ProductPageCapture,
    url: str,
    platform: str,
    *,
    page=None,
) -> None:
    if platform != "jd" or page is None:
        return
    item_id = _extract_jd_item_id(url) or _extract_jd_item_id(capture.final_url)
    if not item_id:
        return
    comments_list, status = await _fetch_jd_comments_via_page(
        page,
        item_id,
        limit=_JD_COMMENTS_LIMIT,
    )
    capture.comments_list = comments_list
    capture.comments_status = status


@dataclass
class ProductPageCapture:
    """商品详情页抓取结果。"""

    final_url: str
    visible_text: str = ""
    title: str = ""
    screenshot_url: str = ""
    head_image_url: str = ""
    detail_image_urls: list[str] = field(default_factory=list)
    source: str = "playwright"
    platform: str = ""
    price_text: str = ""
    shop: str = ""
    price: float | None = None
    sales: int | None = None
    comments_list: list[dict[str, str]] = field(default_factory=list)
    comments_status: str = ""


def _platform_from_url(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if "jd" in host:
        return "jd"
    if "tmall" in host:
        return "tmall"
    return "taobao"


def _normalize_image_urls(urls: list[str]) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for raw in urls:
        url = (raw or "").strip()
        if not url.startswith("http"):
            continue
        if "data:image" in url:
            continue
        if any(skip in url for skip in ("icon", "logo", "sprite", "blank")):
            continue
        if url in seen:
            continue
        seen.add(url)
        normalized.append(url)
    return normalized[:6]


async def _download_image_base64(url: str) -> str:
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=httpx.Timeout(15.0),
        headers=_DEFAULT_HEADERS,
    ) as client:
        response = await client.get(url)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "image/jpeg")
        if "png" in content_type:
            mime = "image/png"
        elif "webp" in content_type:
            mime = "image/webp"
        else:
            mime = "image/jpeg"
        encoded = base64.b64encode(response.content).decode("ascii")
        return f"data:{mime};base64,{encoded}"


async def _wait_for_product_shell(page, timeout_ms: int) -> str:
    """等待商品标题区域出现，返回命中的选择器（空串表示超时后兜底等待）。"""
    for selector in _TITLE_SELECTORS:
        try:
            await page.wait_for_selector(selector, timeout=timeout_ms)
            return selector
        except Exception:
            continue
    print(
        f"[ProductPageScraper] 未匹配标题选择器，兜底等待 1500ms "
        f"timeout_ms={timeout_ms}"
    )
    await page.wait_for_timeout(1500)
    return ""


async def _wait_for_jd_price(page, timeout_ms: int = 8000) -> str:
    """等待京东新版价格节点（product-price--value）渲染。"""
    deadline = time.perf_counter() + timeout_ms / 1000
    while time.perf_counter() < deadline:
        price_text = await page.evaluate(
            """() => {
                const readPrice = (node) => {
                    if (!node) return '';
                    const attr = node.getAttribute('product-price--value');
                    const text = (attr || node.textContent || '').replace(/\\s/g, '');
                    if (text && !text.includes('?')) return text;
                    return '';
                };
                for (const selector of [
                    '.product-price--value',
                    '[class*="product-price--value"]',
                    '[product-price--value]',
                ]) {
                    const node = document.querySelector(selector);
                    const value = readPrice(node);
                    if (value) return value;
                }
                return '';
            }"""
        )
        if price_text:
            return str(price_text).strip()
        await page.wait_for_timeout(400)
    return ""


async def _extract_structured_product_text(page, platform: str) -> dict[str, str]:
    """从渲染后的 DOM 提取结构化字段（优先于纯 body 文本）。"""
    try:
        payload = await page.evaluate(
            """(platform) => {
                const pick = (selectors) => {
                    for (const selector of selectors) {
                        const node = document.querySelector(selector);
                        if (node && node.textContent) {
                            return node.textContent.trim();
                        }
                    }
                    return '';
                };
                const pickJdPrice = () => {
                    const readPrice = (node) => {
                        if (!node) return '';
                        const attr = node.getAttribute('product-price--value');
                        const text = (attr || node.textContent || '').trim();
                        if (text && !text.includes('?')) return text;
                        return '';
                    };
                    for (const selector of [
                        '.product-price--value',
                        '[class*="product-price--value"]',
                        '[product-price--value]',
                    ]) {
                        const node = document.querySelector(selector);
                        const value = readPrice(node);
                        if (value) return value;
                    }
                    return pick([
                        '.p-price .price',
                        '.summary-price .price',
                    ]);
                };
                const titleSelectors = platform === 'jd'
                    ? ['.sku-name', '.itemInfo-wrap .sku-name', 'div.sku-name', 'h1']
                    : ['.tb-main-title', '[class*="MainTitle"]', '#J_Title', 'h1'];
                const shopSelectors = platform === 'jd'
                    ? ['.name a', '.shop-name', '[class*="shopName"]']
                    : ['.shop-name', '[class*="ShopName"]', '.slogo-shopname'];
                return {
                    title: pick(titleSelectors),
                    price: platform === 'jd' ? pickJdPrice() : pick([
                        '.tm-price', '.price', '[class*="Price"]',
                    ]),
                    shop: pick(shopSelectors),
                };
            }""",
            platform,
        )
        if isinstance(payload, dict):
            return {
                "title": str(payload.get("title", "")).strip(),
                "price": str(payload.get("price", "")).strip(),
                "shop": str(payload.get("shop", "")).strip(),
            }
    except Exception:
        pass
    return {"title": "", "price": "", "shop": ""}


async def _collect_visible_text(page, platform: str) -> dict[str, str]:
    structured = await _extract_structured_product_text(page, platform)

    title = structured.get("title", "")
    if not title:
        for selector in _TITLE_SELECTORS:
            try:
                title = (await page.locator(selector).first.inner_text(timeout=1500)).strip()
                if title:
                    break
            except Exception:
                continue

    try:
        body_text = (await page.locator("body").inner_text(timeout=5000)).strip()
    except Exception:
        body_text = ""

    chunks = [title, structured.get("price", ""), structured.get("shop", ""), body_text]
    merged = "\n".join(part for part in chunks if part)
    merged = re.sub(r"\s+", " ", merged).strip()
    return {
        "title": title,
        "visible_text": merged[:12000],
        "price_text": structured.get("price", ""),
        "shop": structured.get("shop", ""),
    }


async def _collect_head_image_url(page, platform: str) -> str:
    """抓取商品主图（头图）URL。"""
    selectors = _HEAD_IMAGE_SELECTORS.get(platform, _HEAD_IMAGE_SELECTORS["taobao"])
    for selector in selectors:
        try:
            found = await page.eval_on_selector_all(
                selector,
                "els => els.map(el => el.currentSrc || el.src || el.getAttribute('data-src')).filter(Boolean)",
            )
            normalized = _normalize_image_urls(found or [])
            if normalized:
                return normalized[0]
        except Exception:
            continue
    return ""


async def _collect_detail_image_urls(page) -> list[str]:
    urls: list[str] = []
    for selector in _DETAIL_IMAGE_SELECTORS:
        try:
            found = await page.eval_on_selector_all(
                selector,
                "els => els.map(el => el.currentSrc || el.src).filter(Boolean)",
            )
            if found:
                urls.extend(found)
        except Exception:
            continue
    if urls:
        return _normalize_image_urls(urls)

    try:
        fallback = await page.eval_on_selector_all(
            "img",
            "els => els.map(el => el.currentSrc || el.src).filter(Boolean)",
        )
        return _normalize_image_urls(fallback or [])
    except Exception:
        return []


async def capture_product_page(url: str) -> Optional[ProductPageCapture]:
    """用 Playwright 打开商品详情页，等待渲染后抓取文本与图片。"""
    if not settings.PRODUCT_SCRAPER_USE_PLAYWRIGHT:
        print("[ProductPageScraper] Playwright 已关闭（PRODUCT_SCRAPER_USE_PLAYWRIGHT=false）")
        return None

    if not is_playwright_available():
        print(
            "[ProductPageScraper] 未安装 Playwright，无法渲染商品页。"
            f" 请执行: {playwright_setup_hint()}"
        )
        return None

    from playwright.async_api import async_playwright

    platform = _platform_from_url(url)
    timeout_ms = settings.PRODUCT_PLAYWRIGHT_TIMEOUT_MS
    use_mobile = platform in {"taobao", "tmall"}
    started = time.perf_counter()
    print(
        f"[ProductPageScraper] 开始抓取 url={url} platform={platform} "
        f"timeout_ms={timeout_ms} mobile={use_mobile}"
    )

    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            print(f"[ProductPageScraper] 浏览器已启动 +{_elapsed_ms(started)}ms")
            try:
                context = await browser.new_context(
                    user_agent=_MOBILE_UA if use_mobile else _DEFAULT_HEADERS["User-Agent"],
                    locale="zh-CN",
                    viewport={"width": 412, "height": 915}
                    if use_mobile
                    else {"width": 1366, "height": 900},
                )
                page = await context.new_page()

                goto_started = time.perf_counter()
                await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                print(
                    f"[ProductPageScraper] 页面 domcontentloaded final_url={page.url} "
                    f"+{_elapsed_ms(goto_started)}ms"
                )

                shell_started = time.perf_counter()
                matched_selector = await _wait_for_product_shell(page, min(timeout_ms, 12000))
                if matched_selector:
                    print(
                        f"[ProductPageScraper] 标题区域已出现 selector={matched_selector!r} "
                        f"+{_elapsed_ms(shell_started)}ms"
                    )

                idle_started = time.perf_counter()
                try:
                    await page.wait_for_load_state("networkidle", timeout=8000)
                    print(
                        f"[ProductPageScraper] networkidle 完成 +{_elapsed_ms(idle_started)}ms"
                    )
                except Exception:
                    print(
                        f"[ProductPageScraper] networkidle 超时（继续抓取） "
                        f"+{_elapsed_ms(idle_started)}ms"
                    )

                scroll_started = time.perf_counter()
                for i in range(3):
                    await page.mouse.wheel(0, 1200)
                    await page.wait_for_timeout(600)
                print(
                    f"[ProductPageScraper] 懒加载滚动完成 rounds=3 "
                    f"+{_elapsed_ms(scroll_started)}ms"
                )

                jd_price_text = ""
                if platform == "jd":
                    price_started = time.perf_counter()
                    jd_price_text = await _wait_for_jd_price(page, timeout_ms=10000)
                    if jd_price_text:
                        print(
                            f"[ProductPageScraper] 京东价格已出现 product-price--value={jd_price_text!r} "
                            f"+{_elapsed_ms(price_started)}ms"
                        )
                    else:
                        print(
                            f"[ProductPageScraper] 京东价格节点未出现 product-price--value "
                            f"+{_elapsed_ms(price_started)}ms"
                        )

                extract_started = time.perf_counter()
                collected = await _collect_visible_text(page, platform)
                if jd_price_text and _parse_numeric_price(jd_price_text) is not None:
                    collected["price_text"] = jd_price_text
                title = collected["title"]
                visible_text = collected["visible_text"]
                text_usable = _is_usable_visible_text(
                    visible_text,
                    min_chars=40,
                    product_title=title,
                )
                print(
                    f"[ProductPageScraper] 文本提取完成 title={title[:60]!r} "
                    f"price_text={collected.get('price_text', '')[:30]!r} "
                    f"text_len={len(visible_text)} usable={text_usable} "
                    f"+{_elapsed_ms(extract_started)}ms"
                )
                if not text_usable:
                    print(
                        f"[ProductPageScraper] 页面文本不可用 final_url={page.url} "
                        f"text_len={len(visible_text)} title={title[:60]!r}"
                    )

                image_started = time.perf_counter()
                head_image_url = await _collect_head_image_url(page, platform)
                detail_image_urls = await _collect_detail_image_urls(page)
                print(
                    f"[ProductPageScraper] 头图收集 url={head_image_url[:80]!r} "
                    f"详情图 count={len(detail_image_urls)} +{_elapsed_ms(image_started)}ms"
                )

                screenshot_started = time.perf_counter()
                screenshot_bytes = await page.screenshot(
                    full_page=False,
                    type="jpeg",
                    quality=72,
                )
                screenshot_url = save_product_screenshot(
                    screenshot_bytes,
                    platform=platform,
                    url=page.url,
                )
                print(
                    f"[ProductPageScraper] 截图完成 size_kb={len(screenshot_bytes) // 1024} "
                    f"url={screenshot_url} +{_elapsed_ms(screenshot_started)}ms"
                )

                print(
                    f"[ProductPageScraper] 抓取完成 final_url={page.url} "
                    f"total_ms={_elapsed_ms(started)}"
                )
                capture = ProductPageCapture(
                    final_url=page.url,
                    visible_text=visible_text,
                    title=title,
                    screenshot_url=screenshot_url,
                    head_image_url=head_image_url,
                    detail_image_urls=detail_image_urls,
                    source="playwright",
                    platform=platform,
                    price_text=collected.get("price_text", ""),
                    shop=collected.get("shop", ""),
                )
                await _enrich_capture_price_sales(capture, url, platform, page=page)
                await _enrich_capture_comments(capture, url, platform, page=page)
                return capture
            finally:
                await browser.close()
    except Exception as exc:
        message = str(exc)
        if "Executable doesn't exist" in message:
            print(
                "[ProductPageScraper] Chromium 浏览器未安装。"
                f" 请执行: {playwright_setup_hint()}"
            )
        else:
            print(f"[ProductPageScraper] Playwright 抓取失败: {exc}")
        return None


async def build_vision_image_payload(capture: ProductPageCapture) -> list[str]:
    """组装供多模态模型识别的图片（截图 + 详情图）。"""
    images: list[str] = []
    screenshot_path = screenshot_local_path(capture.screenshot_url)
    if screenshot_path and screenshot_path.is_file():
        encoded = base64.b64encode(screenshot_path.read_bytes()).decode("ascii")
        images.append(f"data:image/jpeg;base64,{encoded}")

    for image_url in capture.detail_image_urls[:2]:
        try:
            print(f"[ProductPageScraper] 下载详情图 url={image_url[:120]}")
            images.append(await _download_image_base64(image_url))
        except httpx.HTTPError as exc:
            print(f"[ProductPageScraper] 详情图下载失败 url={image_url[:120]} err={exc}")
            continue
    print(f"[ProductPageScraper] 视觉输入图片数={len(images[:3])}")
    return images[:3]
