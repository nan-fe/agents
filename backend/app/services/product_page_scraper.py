"""Playwright 商品详情页抓取：等待渲染后提取可见文本与详情图。"""

from __future__ import annotations

import asyncio
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

_JD_TITLE_SELECTORS = (
    ".sku-name",
    ".itemInfo-wrap .sku-name",
    "div.sku-name",
    "[class*='goods-name']",
    "[class*='product-intro'] h1",
    ".p-name",
    "h1",
)

_TAOBAO_TITLE_SELECTORS = (
    ".tb-main-title",
    "[class*='MainTitle']",
    "[class*='ItemTitle']",
    "#J_Title",
    "h1",
)

_JD_XHR_TIMEOUT_MS = 8000
_JD_PAGE_EVAL_TIMEOUT_SEC = 20.0

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

_JD_BLOCKED_URL_MARKERS = (
    "pc-frequent-pro.pf.jd.com",
    "reason=403",
    "risk_handler",
    "passport.jd.com/new/login",
)

_JD_BLOCKED_TITLE_MARKERS = (
    "PC频控页",
    "访问受限",
    "验证",
    "请登录",
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


def _parse_jd_document_title(raw_title: str) -> str:
    """从 document.title 提取商品名（常见格式：「商品名 - 京东」）。"""
    title = re.sub(r"\s+", " ", (raw_title or "").strip())
    if not title:
        return ""
    for suffix in (
        r"\s*[-–—|｜]\s*京东.*$",
        r"\s*[-–—|｜]\s*JD\.COM.*$",
        r"\s*【.*?】\s*京东.*$",
    ):
        stripped = re.sub(suffix, "", title, flags=re.IGNORECASE).strip()
        if stripped and stripped != title:
            title = stripped
            break
    if len(title) >= 4 and not any(marker in title for marker in _BLOCKED_TEXT_MARKERS):
        if not is_jd_blocked_page("", title=title):
            return title
    return ""


def is_jd_blocked_page(url: str, *, title: str = "") -> bool:
    """判断京东是否跳转到频控/登录/403 拦截页。"""
    lowered_url = (url or "").lower()
    if any(marker in lowered_url for marker in _JD_BLOCKED_URL_MARKERS):
        return True
    normalized_title = (title or "").strip()
    if normalized_title and any(
        marker in normalized_title for marker in _JD_BLOCKED_TITLE_MARKERS
    ):
        return True
    return False


def _jd_mobile_item_url(item_id: str) -> str:
    return f"https://item.m.jd.com/product/{item_id}.html"


async def _ensure_jd_product_page(
    page,
    item_id: str,
    timeout_ms: int,
    *,
    stage: str,
) -> bool:
    """若当前为京东拦截页则尝试切到移动端详情页。"""
    if not item_id or not is_jd_blocked_page(page.url):
        return True

    mobile_url = _jd_mobile_item_url(item_id)
    print(
        f"[ProductPageScraper] 京东 {stage} 检测到拦截页 final_url={page.url} "
        f"回退移动端 url={mobile_url}"
    )
    started = time.perf_counter()
    await page.goto(
        mobile_url,
        wait_until="domcontentloaded",
        timeout=timeout_ms,
    )
    await page.wait_for_timeout(2500)
    blocked = is_jd_blocked_page(page.url)
    print(
        f"[ProductPageScraper] 京东移动端 {stage} final_url={page.url} "
        f"blocked={blocked} +{_elapsed_ms(started)}ms"
    )
    return not blocked


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


def _is_jd_mgets_price_url(url: str) -> bool:
    lowered = (url or "").lower()
    return "prices/mgets" in lowered or (
        "p.3.cn" in lowered and "skuids" in lowered
    )


def _is_jd_ware_business_url(url: str) -> bool:
    return "api.m.jd.com" in (url or "") and "warebusiness" in (url or "").lower()


def _is_valid_jd_price_text(text: str) -> bool:
    cleaned = (text or "").strip()
    if not cleaned or "?" in cleaned:
        return False
    if any(marker in cleaned for marker in ("登录查看", "登录后", "请登录")):
        return False
    return _parse_numeric_price(cleaned) is not None


def _parse_jd_mgets_payload(payload: Any) -> float | None:
    """解析 p.3.cn/prices/mgets 返回的 JSON 列表。"""
    if not isinstance(payload, list) or not payload:
        return None
    first = payload[0]
    if not isinstance(first, dict):
        return None
    return _parse_numeric_price(str(first.get("p") or first.get("op") or ""))


def _parse_jd_ware_business_payload(payload: Any) -> tuple[float | None, int | None]:
    """从 pc_detailpage_wareBusiness 响应中提取价格/评价数。"""
    price: float | None = None
    sales: int | None = None

    def walk(node: Any, depth: int = 0) -> None:
        nonlocal price, sales
        if depth > 8 or node is None:
            return
        if isinstance(node, dict):
            for key, value in node.items():
                key_lower = str(key).lower()
                if price is None and key_lower in {"p", "jdprice", "op", "price", "finalprice"}:
                    if isinstance(value, (str, int, float)):
                        candidate = _parse_numeric_price(str(value))
                        if candidate is not None:
                            price = candidate
                if sales is None and key_lower in {
                    "commentcount",
                    "commentcountstr",
                    "allcommentcount",
                    "evaluatecount",
                }:
                    if isinstance(value, (str, int, float)):
                        parsed = _parse_sales_count(str(value))
                        if parsed is not None:
                            sales = parsed
                        elif str(value).isdigit():
                            sales = int(value)
                walk(value, depth + 1)
        elif isinstance(node, list):
            for item in node[:20]:
                walk(item, depth + 1)

    walk(payload)
    return price, sales


def _parse_jd_mobile_item_info(payload: Any) -> tuple[float | None, int | None]:
    """解析移动端 window._itemInfo 中的价格/销量线索。"""
    if not isinstance(payload, dict):
        return None, None
    price: float | None = None
    sales: int | None = None

    def walk(node: Any, depth: int = 0) -> None:
        nonlocal price, sales
        if depth > 8 or node is None:
            return
        if isinstance(node, dict):
            for key, value in node.items():
                key_lower = str(key).lower()
                if price is None and key_lower in {"p", "jdprice", "op", "price"}:
                    if isinstance(value, (str, int, float)):
                        text = str(value)
                        if _is_valid_jd_price_text(text):
                            price = _parse_numeric_price(text)
                if sales is None and key_lower in {
                    "commentcount",
                    "commentcountstr",
                    "allcommentcount",
                    "evaluatecount",
                    "allnum",
                }:
                    if isinstance(value, (str, int, float)):
                        parsed = _parse_sales_count(str(value))
                        if parsed is not None and parsed > 0:
                            sales = parsed
                walk(value, depth + 1)
        elif isinstance(node, list):
            for item in node[:20]:
                walk(item, depth + 1)

    walk(payload)
    return price, sales


@dataclass
class _JdNetworkCapture:
    price: float | None = None
    sales: int | None = None


def _jd_playwright_cookies() -> list[dict[str, Any]]:
    raw = (settings.PRODUCT_JD_COOKIE or "").strip()
    if not raw:
        return []
    cookies: list[dict[str, Any]] = []
    for part in raw.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        name, value = part.split("=", 1)
        name = name.strip()
        value = value.strip()
        if not name:
            continue
        cookies.append(
            {
                "name": name,
                "value": value,
                "domain": ".jd.com",
                "path": "/",
            }
        )
    return cookies


def _attach_jd_network_listeners(page, capture: _JdNetworkCapture) -> None:
    async def on_response(response) -> None:
        url = response.url
        try:
            if not response.ok:
                return
            if _is_jd_mgets_price_url(url):
                network_price = _parse_jd_mgets_payload(await response.json())
                if network_price is not None:
                    capture.price = network_price
                    print(
                        f"[ProductPageScraper] 京东价格接口(网络监听) price={network_price}"
                    )
                return
            if _is_jd_ware_business_url(url):
                ware_price, ware_sales = _parse_jd_ware_business_payload(
                    await response.json()
                )
                if ware_price is not None:
                    capture.price = ware_price
                    print(
                        f"[ProductPageScraper] 京东 wareBusiness 价格 price={ware_price}"
                    )
                if ware_sales is not None:
                    capture.sales = ware_sales
                    print(
                        f"[ProductPageScraper] 京东 wareBusiness 销量 sales={ware_sales}"
                    )
        except Exception:
            return

    page.on("response", on_response)


async def _jd_page_requires_login_for_price(page) -> bool:
    try:
        return bool(
            await page.evaluate(
                """() => {
                    const text = document.body?.innerText || '';
                    return text.includes('登录查看更多图片')
                        || text.includes('登录查看价格')
                        || text.includes('登录后查看价格');
                }"""
            )
        )
    except Exception:
        return False


async def _fetch_jd_price_via_page_xhr(page, item_id: str) -> float | None:
    """在页面上下文中用 XHR 请求价格（与页面 JS 同源）。"""
    try:
        result = await asyncio.wait_for(
            page.evaluate(
                """async (args) => {
                    const sku = args.sku;
                    const timeoutMs = args.timeoutMs;
                    const fetchOne = (url) => new Promise((resolve) => {
                        const xhr = new XMLHttpRequest();
                        const timer = setTimeout(() => {
                            try { xhr.abort(); } catch (e) {}
                            resolve({error: 'timeout'});
                        }, timeoutMs);
                        xhr.open('GET', url, true);
                        xhr.withCredentials = true;
                        xhr.onload = () => {
                            clearTimeout(timer);
                            resolve({status: xhr.status, body: xhr.responseText || ''});
                        };
                        xhr.onerror = () => {
                            clearTimeout(timer);
                            resolve({error: 'xhr-error'});
                        };
                        xhr.send();
                    });
                    const urls = [
                        `https://p.3.cn/prices/mgets?skuIds=J_${sku}&type=1`,
                        `https://p.3.cn/prices/mgets?skuIds=J_${sku}`,
                    ];
                    for (const url of urls) {
                        try {
                            const response = await fetchOne(url);
                            if (response?.status === 200 && response.body) {
                                return {url, body: response.body};
                            }
                        } catch (e) {}
                    }
                    return null;
                }""",
                {"sku": item_id, "timeoutMs": _JD_XHR_TIMEOUT_MS},
            ),
            timeout=_JD_PAGE_EVAL_TIMEOUT_SEC,
        )
        if not isinstance(result, dict):
            return None
        body = str(result.get("body") or "").strip()
        if not body:
            return None
        payload = json.loads(body)
        price = _parse_jd_mgets_payload(payload)
        if price is not None:
            print(f"[ProductPageScraper] 京东价格接口(页面XHR) sku={item_id} price={price}")
        return price
    except asyncio.TimeoutError:
        print(
            f"[ProductPageScraper] 京东价格 XHR 超时 sku={item_id} "
            f"timeout_sec={_JD_PAGE_EVAL_TIMEOUT_SEC}"
        )
        return None
    except Exception as exc:
        print(
            f"[ProductPageScraper] 京东价格 XHR 失败 sku={item_id} "
            f"{type(exc).__name__}: {exc!r}"
        )
        return None


async def _fetch_jd_mobile_price_sales(context, item_id: str) -> tuple[float | None, int | None]:
    """移动端详情页回退：部分商品在 m.jd.com 的 _itemInfo 中含价格/销量。"""
    mobile_page = await context.new_page()
    price: float | None = None
    sales: int | None = None
    try:
        await mobile_page.goto(
            f"https://item.m.jd.com/product/{item_id}.html",
            wait_until="domcontentloaded",
            timeout=20_000,
        )
        await mobile_page.wait_for_timeout(2500)
        payload = await mobile_page.evaluate(
            """() => {
                try {
                    return window._itemInfo || null;
                } catch (e) {
                    return null;
                }
            }"""
        )
        price, sales = _parse_jd_mobile_item_info(payload)
        dom_price = await mobile_page.evaluate(
            """() => {
                const nodes = [
                    document.querySelector('#priceSale2'),
                    document.querySelector('#priceSale1'),
                    document.querySelector('.price'),
                ];
                for (const node of nodes) {
                    const text = (node?.textContent || '').replace(/\\s+/g, '').trim();
                    if (text) return text;
                }
                return '';
            }"""
        )
        if price is None and _is_valid_jd_price_text(str(dom_price or "")):
            price = _parse_numeric_price(str(dom_price))
        if price is not None or sales is not None:
            print(
                f"[ProductPageScraper] 京东移动端回退 sku={item_id} "
                f"price={price} sales={sales}"
            )
    except Exception as exc:
        print(
            f"[ProductPageScraper] 京东移动端回退失败 sku={item_id} "
            f"{type(exc).__name__}: {exc!r}"
        )
    finally:
        await mobile_page.close()
    return price, sales


async def _try_capture_jd_price_from_network(page, *, timeout_ms: int) -> float | None:
    """等待页面发起的 p.3.cn/prices/mgets 响应（与页面 JS 共用 Cookie/会话）。"""
    try:
        response = await page.wait_for_response(
            lambda r: _is_jd_mgets_price_url(r.url) and r.ok,
            timeout=timeout_ms,
        )
        payload = await response.json()
        price = _parse_jd_mgets_payload(payload)
        if price is not None:
            print(f"[ProductPageScraper] 京东价格接口(页面XHR) price={price}")
        return price
    except Exception:
        return None


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
        body = await asyncio.wait_for(
            page.evaluate(
                """async ({ itemId, limit, referer, timeoutMs }) => {
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
                    const controller = new AbortController();
                    const timer = setTimeout(() => controller.abort(), timeoutMs);
                    try {
                        const resp = await fetch(url, {
                            credentials: 'include',
                            headers: { Referer: referer },
                            signal: controller.signal,
                        });
                        return await resp.text();
                    } finally {
                        clearTimeout(timer);
                    }
                }""",
                {
                    "itemId": item_id,
                    "limit": limit,
                    "referer": referer,
                    "timeoutMs": _JD_XHR_TIMEOUT_MS,
                },
            ),
            timeout=_JD_PAGE_EVAL_TIMEOUT_SEC,
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

            if attempt < _JD_COMMENT_RETRY_COUNT and last_status == "api_blocked":
                print(
                    f"[ProductPageScraper] 京东评论接口被限流 sku={item_id}，"
                    f" 重试 {attempt + 1}/{_JD_COMMENT_RETRY_COUNT}"
                )
                await page.wait_for_timeout(int(_JD_COMMENT_RETRY_SLEEP_SEC * 1000))
            elif last_status.startswith("http_"):
                break

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


async def _fetch_jd_price_sales_via_page(
    page,
    item_id: str,
    *,
    skip_price: bool = False,
) -> tuple[float | None, int | None]:
    """在 Playwright 浏览器上下文中请求京东价格/评价接口（比 httpx 直连更稳定）。"""
    price: float | None = None
    sales: int | None = None
    referer = f"https://item.jd.com/{item_id}.html"
    headers = {"Referer": referer}

    if not skip_price:
        price = await _fetch_jd_price_via_page_xhr(page, item_id)
        if price is None:
            try:
                price_resp = await page.request.get(
                    "https://p.3.cn/prices/mgets",
                    params={"skuIds": f"J_{item_id}", "type": "1"},
                    headers=headers,
                    timeout=12_000,
                )
                if price_resp.ok:
                    payload = await price_resp.json()
                    price = _parse_jd_mgets_payload(payload)
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
                price = _parse_jd_mgets_payload(payload)
                if price is not None:
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
    prefetched_price: float | None = None,
    prefetched_sales: int | None = None,
    skip_jd_api: bool = False,
) -> None:
    price = _parse_price_from_visible_text(capture.visible_text)
    sales = _parse_sales_from_visible_text(capture.visible_text)

    if capture.price_text:
        dom_price = _parse_numeric_price(capture.price_text)
        if dom_price is not None:
            price = dom_price

    if prefetched_price is not None and price is None:
        price = prefetched_price
    if prefetched_sales is not None and sales is None:
        sales = prefetched_sales

    if platform == "jd":
        item_id = _extract_jd_item_id(url) or _extract_jd_item_id(capture.final_url)
        if item_id:
            need_price = price is None
            need_sales = sales is None
            if (need_price or need_sales) and not skip_jd_api:
                if page is not None:
                    api_price, api_sales = await _fetch_jd_price_sales_via_page(
                        page,
                        item_id,
                        skip_price=not need_price,
                    )
                else:
                    api_price, api_sales = await _fetch_jd_price_sales(item_id)
                if need_price and api_price is not None:
                    price = api_price
                if need_sales and api_sales is not None:
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
        if page is not None and await _jd_page_requires_login_for_price(page):
            print(
                "[ProductPageScraper] 京东页面提示需登录后查看价格/图片；"
                "可在 backend/.env 配置 PRODUCT_JD_COOKIE（浏览器 jd.com 的 Cookie 字符串）"
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
    if is_jd_blocked_page(capture.final_url, title=capture.title):
        capture.comments_status = "page_blocked"
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


def _title_selectors_for_platform(platform: str) -> tuple[str, ...]:
    if platform == "jd":
        return _JD_TITLE_SELECTORS
    if platform in {"taobao", "tmall"}:
        return _TAOBAO_TITLE_SELECTORS
    return _TITLE_SELECTORS


async def _wait_for_product_shell(page, timeout_ms: int, *, platform: str = "") -> str:
    """等待商品标题区域出现，返回命中的选择器（空串表示超时后兜底等待）。"""
    selectors = _title_selectors_for_platform(platform)
    per_selector_ms = min(2500, max(800, timeout_ms // 4))
    for selector in selectors:
        try:
            await page.wait_for_selector(selector, timeout=per_selector_ms)
            return selector
        except Exception:
            continue
    print(
        f"[ProductPageScraper] 未匹配标题选择器 platform={platform or 'unknown'} "
        f"兜底等待 1500ms per_selector_ms={per_selector_ms}"
    )
    await page.wait_for_timeout(1500)
    return ""


async def _wait_for_jd_price(
    page,
    item_id: str = "",
    timeout_ms: int = 8000,
) -> str:
    """等待京东价格节点渲染（新版 product-price--value + 旧版 .J-p-skuId）。"""
    deadline = time.perf_counter() + timeout_ms / 1000
    while time.perf_counter() < deadline:
        price_text = await page.evaluate(
            """(skuId) => {
                const readPrice = (node) => {
                    if (!node) return '';
                    const attr = node.getAttribute('product-price--value');
                    const text = (attr || node.textContent || '').replace(/\\s/g, '');
                    if (!text || text.includes('?') || text.includes('登录')) return '';
                    if (!/\\d/.test(text)) return '';
                    return text;
                };
                const selectors = [
                    '.product-price--value',
                    '[class*="product-price--value"]',
                    '[product-price--value]',
                ];
                if (skuId) {
                    selectors.push(
                        `.price.J-p-${skuId}`,
                        `.J-p-${skuId}`,
                        `#J_FinalPrice`,
                    );
                }
                selectors.push('.p-price .price', '.summary-price .price', '.p-price span.price');
                for (const selector of selectors) {
                    const node = document.querySelector(selector);
                    const value = readPrice(node);
                    if (value) return value;
                }
                return '';
            }""",
            item_id,
        )
        if price_text and _is_valid_jd_price_text(str(price_text)):
            return str(price_text).strip()
        await page.wait_for_timeout(400)
    return ""


async def _extract_structured_product_text(page, platform: str) -> dict[str, str]:
    """从渲染后的 DOM 提取结构化字段（优先于纯 body 文本）。"""
    try:
        payload = await page.evaluate(
            """(args) => {
                const platform = args.platform;
                const skuId = args.skuId || '';
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
                        if (!text || text.includes('?') || text.includes('登录')) return '';
                        if (!/\\d/.test(text)) return '';
                        return text;
                    };
                    const selectors = [
                        '.product-price--value',
                        '[class*="product-price--value"]',
                        '[product-price--value]',
                    ];
                    if (skuId) {
                        selectors.push(
                            `.price.J-p-${skuId}`,
                            `.J-p-${skuId}`,
                            `#J_FinalPrice`,
                        );
                    }
                    selectors.push('.p-price .price', '.summary-price .price', '.p-price span.price');
                    for (const selector of selectors) {
                        const node = document.querySelector(selector);
                        const value = readPrice(node);
                        if (value) return value;
                    }
                    return '';
                };
                const titleSelectors = platform === 'jd'
                    ? [
                        '.sku-name',
                        '.itemInfo-wrap .sku-name',
                        'div.sku-name',
                        '[class*="goods-name"]',
                        '[class*="product-intro"] h1',
                        '.p-name',
                        'h1',
                    ]
                    : ['.tb-main-title', '[class*="MainTitle"]', '#J_Title', 'h1'];
                const shopSelectors = platform === 'jd'
                    ? ['.name a', '.shop-name', '[class*="shopName"]']
                    : ['.shop-name', '[class*="ShopName"]', '.slogo-shopname'];
                let title = pick(titleSelectors);
                if (!title && platform === 'jd') {
                    try {
                        const itemInfo = window._itemInfo;
                        title = (
                            itemInfo?.product?.name
                            || itemInfo?.wareInfo?.name
                            || itemInfo?.wareInfo?.wname
                            || ''
                        ).trim();
                    } catch (e) {}
                }
                if (!title && platform === 'jd') {
                    const docTitle = (document.title || '').trim();
                    title = docTitle.replace(/\\s*[-–—|｜]\\s*京东.*$/i, '').trim();
                }
                return {
                    title,
                    price: platform === 'jd' ? pickJdPrice() : pick([
                        '.tm-price', '.price', '[class*="Price"]',
                    ]),
                    shop: pick(shopSelectors),
                };
            }""",
            {"platform": platform, "skuId": _extract_jd_item_id(page.url) or ""},
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
        selectors = _title_selectors_for_platform(platform)
        for selector in selectors:
            try:
                title = (await page.locator(selector).first.inner_text(timeout=1500)).strip()
                if title:
                    break
            except Exception:
                continue
    if not title and platform == "jd":
        try:
            doc_title = (await page.title()).strip()
        except Exception:
            doc_title = ""
        title = _parse_jd_document_title(doc_title)

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
                jd_cookies = _jd_playwright_cookies()
                if jd_cookies:
                    await context.add_cookies(jd_cookies)
                    print(
                        f"[ProductPageScraper] 已注入京东 Cookie count={len(jd_cookies)}"
                    )
                page = await context.new_page()

                jd_item_id = _extract_jd_item_id(url) if platform == "jd" else None
                jd_network_price: float | None = None
                jd_prefetched_price: float | None = None
                jd_prefetched_sales: int | None = None
                jd_network_capture = _JdNetworkCapture()
                if jd_item_id:
                    _attach_jd_network_listeners(page, jd_network_capture)

                goto_started = time.perf_counter()
                if jd_item_id:
                    try:
                        async with page.expect_response(
                            lambda r: _is_jd_mgets_price_url(r.url) and r.ok,
                            timeout=min(timeout_ms, 15000),
                        ) as price_resp_info:
                            await page.goto(
                                url, wait_until="domcontentloaded", timeout=timeout_ms
                            )
                        try:
                            price_resp = await price_resp_info.value
                            jd_network_price = _parse_jd_mgets_payload(
                                await price_resp.json()
                            )
                            if jd_network_price is not None:
                                print(
                                    f"[ProductPageScraper] 京东价格接口(页面XHR) "
                                    f"sku={jd_item_id} price={jd_network_price} "
                                    f"+{_elapsed_ms(goto_started)}ms"
                                )
                        except Exception:
                            print(
                                f"[ProductPageScraper] 京东价格 XHR 未在导航期间返回 "
                                f"sku={jd_item_id}（将回退 API/DOM）"
                            )
                    except Exception:
                        await page.goto(
                            url, wait_until="domcontentloaded", timeout=timeout_ms
                        )
                else:
                    await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                print(
                    f"[ProductPageScraper] 页面 domcontentloaded final_url={page.url} "
                    f"+{_elapsed_ms(goto_started)}ms"
                )

                if jd_item_id and is_jd_blocked_page(page.url):
                    if not await _ensure_jd_product_page(
                        page,
                        jd_item_id,
                        timeout_ms,
                        stage="PC导航后",
                    ):
                        return None

                shell_started = time.perf_counter()
                matched_selector = await _wait_for_product_shell(
                    page,
                    min(timeout_ms, 12000),
                    platform=platform,
                )
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

                if jd_item_id:
                    await page.wait_for_timeout(800)
                    if not await _ensure_jd_product_page(
                        page,
                        jd_item_id,
                        timeout_ms,
                        stage="networkidle后",
                    ):
                        return None

                if jd_item_id and jd_network_price is None:
                    late_network_price = await _try_capture_jd_price_from_network(
                        page, timeout_ms=3000
                    )
                    if late_network_price is not None:
                        jd_network_price = late_network_price
                        print(
                            f"[ProductPageScraper] 京东价格接口(页面XHR/networkidle后) "
                            f"sku={jd_item_id} price={jd_network_price}"
                        )

                if jd_item_id and jd_network_capture.price is not None:
                    jd_network_price = jd_network_capture.price

                if jd_item_id:
                    prefetch_started = time.perf_counter()
                    skip_price_prefetch = (
                        jd_network_price is not None or jd_network_capture.price is not None
                    )
                    api_price, api_sales = await _fetch_jd_price_sales_via_page(
                        page,
                        jd_item_id,
                        skip_price=skip_price_prefetch,
                    )
                    jd_prefetched_price = (
                        jd_network_price
                        if jd_network_price is not None
                        else jd_network_capture.price
                        if jd_network_capture.price is not None
                        else api_price
                    )
                    jd_prefetched_sales = api_sales or jd_network_capture.sales
                    if jd_prefetched_price is None or jd_prefetched_sales is None:
                        mobile_price, mobile_sales = await _fetch_jd_mobile_price_sales(
                            context, jd_item_id
                        )
                        if jd_prefetched_price is None:
                            jd_prefetched_price = mobile_price
                        if jd_prefetched_sales is None:
                            jd_prefetched_sales = mobile_sales
                    print(
                        f"[ProductPageScraper] 京东价格预取完成 price={jd_prefetched_price} "
                        f"sales={jd_prefetched_sales} +{_elapsed_ms(prefetch_started)}ms"
                    )

                # 懒加载滚动：主要用于详情图与评论区，不作为价格主路径
                scroll_started = time.perf_counter()
                if not (jd_item_id and "item.m.jd.com" in page.url):
                    for _ in range(3):
                        await page.mouse.wheel(0, 1200)
                        await page.wait_for_timeout(600)
                else:
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
                    await page.wait_for_timeout(800)
                print(
                    f"[ProductPageScraper] 懒加载滚动完成 rounds=3 "
                    f"+{_elapsed_ms(scroll_started)}ms"
                )

                if jd_item_id and not await _ensure_jd_product_page(
                    page,
                    jd_item_id,
                    timeout_ms,
                    stage="滚动后",
                ):
                    return None

                jd_price_text = ""
                if platform == "jd":
                    price_started = time.perf_counter()
                    jd_price_text = await _wait_for_jd_price(
                        page,
                        item_id=jd_item_id or "",
                        timeout_ms=10000,
                    )
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
                if platform == "jd" and is_jd_blocked_page(page.url, title=title):
                    print(
                        f"[ProductPageScraper] 京东页面仍被拦截 title={title[:60]!r} "
                        f"final_url={page.url}"
                    )
                    return None

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
                await _enrich_capture_price_sales(
                    capture,
                    url,
                    platform,
                    page=page,
                    prefetched_price=jd_prefetched_price,
                    prefetched_sales=jd_prefetched_sales,
                    skip_jd_api=bool(jd_item_id),
                )
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
