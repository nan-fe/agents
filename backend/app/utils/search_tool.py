import asyncio
import re
from typing import Any, Dict
from urllib.parse import parse_qs, urlparse

from langchain_community.tools import DuckDuckGoSearchRun

from app.config import settings
from app.utils.retry_policy import retry_with_backoff

try:
    from ddgs import DDGS  # type: ignore
except ImportError:
    from duckduckgo_search import DDGS

# from selenium import webdriver
# from selenium.webdriver.chrome.options import Options
# from selenium.webdriver.chrome.service import Service
# from webdriver_manager.chrome import ChromeDriverManager
# from selenium.webdriver.support.ui import WebDriverWait
# from selenium.webdriver.support import expected_conditions as EC
# from selenium.webdriver.common.by import By
# from selenium.common.exceptions import TimeoutException


# def extract_product_params(url: str) -> Dict[str, Any]:
#     """
#     从 URL 中提取商品参数信息

#     Args:
#         url: 商品链接 URL

#     Returns:
#         提取的商品参数字典
#     """
#     params = {}

#     try:
#         # 解析 URL
#         parsed_url = urlparse(url)
#         query_params = parse_qs(parsed_url.query)

#         # 处理淘宝 URL
#         if "taobao.com" in parsed_url.netloc:
#             # 处理 pcdetail.taobao.com 链接（会重定向）
#             if "pcdetail.taobao.com" in parsed_url.netloc:
#                 params["url_type"] = "taobao_pcdetail"
#                 params["note"] = "该链接会重定向到标准商品页面"

#                 # 尝试从 URL 路径中提取可能的参数
#                 path = parsed_url.path
#                 if path and path.endswith(".html"):
#                     # 提取文件名部分（可能包含编码的商品信息）
#                     filename = path.split("/")[-1].replace(".html", "")
#                     params["encoded_params"] = filename

#             # 提取商品 ID
#             item_id_match = re.search(r"id=(\d+)", url)
#             if item_id_match:
#                 params["item_id"] = item_id_match.group(1)

#             # 提取店铺 ID
#             shop_id_match = re.search(r"shop_id=(\d+)", url)
#             if shop_id_match:
#                 params["shop_id"] = shop_id_match.group(1)

#             # 提取其他参数
#             for key, value in query_params.items():
#                 if key in ["id", "shop_id", "spm", "scm"]:
#                     params[key] = value[0]

#         # 处理京东 URL
#         elif "jd.com" in parsed_url.netloc:
#             # 提取商品 ID
#             product_id_match = re.search(r"/(\d+)\.html", url)
#             if product_id_match:
#                 params["product_id"] = product_id_match.group(1)

#         # 处理天猫 URL
#         elif "tmall.com" in parsed_url.netloc:
#             # 提取商品 ID
#             item_id_match = re.search(r"id=(\d+)", url)
#             if item_id_match:
#                 params["item_id"] = item_id_match.group(1)

#         # 通用参数提取
#         if "q" in query_params:
#             params["search_query"] = query_params["q"][0]

#     except Exception as e:
#         print(f"提取参数出错: {str(e)}")

#     return params


# def search_duckduckgo(
#     query: str, max_results: int = 5, site: str = None
# ) -> List[Dict[str, Any]]:
#     """
#     使用 DuckDuckGo 搜索获取相关信息，并从 URL 中提取商品参数

#     Args:
#         query: 搜索查询词
#         max_results: 最大返回结果数
#         site: 限定的网站域名，如 "taobao.com"

#     Returns:
#         搜索结果列表，每个结果包含标题、链接、摘要和商品参数
#     """
#     try:
#         with DDGS() as ddgs:
#             # 构建搜索查询
#             search_query = query
#             if site:
#                 search_query = f"{query} site:{site}"

#             results = []
#             for result in ddgs.text(search_query, max_results=max_results):
#                 print("originaltext", result)
#                 url = result.get("href", "")
#                 # 提取商品参数
#                 product_params = extract_product_params(url)

#                 results.append(
#                     {
#                         "title": result.get("title", ""),
#                         "url": url,
#                         "snippet": result.get("body", ""),
#                         "product_params": product_params,  # 添加商品参数
#                     }
#                 )
#             return results
#     except Exception as e:
#         print(f"搜索出错: {str(e)}")
#         return []


# def search_news(query: str, max_results: int = 3) -> List[Dict[str, Any]]:
#     """
#     使用 DuckDuckGo 搜索获取新闻信息

#     Args:
#         query: 搜索查询词
#         max_results: 最大返回结果数

#     Returns:
#         新闻结果列表，每个结果包含标题、链接、摘要和日期
#     """
#     try:
#         with DDGS() as ddgs:
#             results = []
#             for result in ddgs.news(query, max_results=max_results):
#                 results.append(
#                     {
#                         "title": result.get("title", ""),
#                         "url": result.get("url", ""),
#                         "snippet": result.get("body", ""),
#                         "date": result.get("date", ""),
#                     }
#                 )
#             return results
#     except Exception as e:
#         print(f"新闻搜索出错: {str(e)}")
#         return []


# def search_images(query: str, max_results: int = 3) -> List[Dict[str, Any]]:
#     """
#     使用 DuckDuckGo 搜索获取图片信息

#     Args:
#         query: 搜索查询词
#         max_results: 最大返回结果数

#     Returns:
#         图片结果列表，每个结果包含标题、图片URL和来源URL
#     """
#     try:
#         with DDGS() as ddgs:
#             results = []
#             for result in ddgs.images(query, max_results=max_results):
#                 results.append(
#                     {
#                         "title": result.get("title", ""),
#                         "image_url": result.get("image", ""),
#                         "source_url": result.get("url", ""),
#                     }
#                 )
#             return results
#     except Exception as e:
#         print(f"图片搜索出错: {str(e)}")
#         return []


_TAOBAO_ITEM_ID_RE = re.compile(r"[?&]id=(\d+)")


def _extract_taobao_item_id(url: str) -> str | None:
    parsed = urlparse(url)
    q = parse_qs(parsed.query)
    if "id" in q and q["id"]:
        return q["id"][0]
    m = _TAOBAO_ITEM_ID_RE.search(url)
    return m.group(1) if m else None


def is_taobao_item_detail_url(url: str) -> bool:
    """是否为淘宝 C 店或天猫商品详情页链接（含 item.htm 与 numeric id）。"""
    if not url:
        return False
    u = url.lower()
    if "id=" not in u:
        return False
    if "item.taobao.com" in u and "item.htm" in u:
        return True
    if "detail.tmall.com" in u and "item.htm" in u:
        return True
    return False


def canonical_taobao_item_url(url: str) -> str:
    """去掉多余 query，规范为 item.taobao.com 或 detail.tmall.com 的 item.htm?id=。"""
    item_id = _extract_taobao_item_id(url)
    if not item_id:
        return url
    parsed = urlparse(url)
    host = "detail.tmall.com" if "tmall.com" in parsed.netloc.lower() else "item.taobao.com"
    return f"https://{host}/item.htm?id={item_id}"


def retrieval_copy_matches_category(
    category: str,
    title: str,
    summary: str,
    *,
    min_char_overlap_ratio: float = 0.45,
) -> bool:
    """
    判断检索得到的标题+摘要是否与商品类别一致（启发式，用于过滤 DDG 偏题结果）。

    1. 类别词完整出现在 title 或 summary 中 → True；
    2. 否则：类别中非空白字符在合并文案中的出现比例 ≥ min_char_overlap_ratio → True。
    """
    cat = (category or "").strip()
    if not cat:
        return False
    blob = f"{title}\n{summary}".strip()
    if not blob:
        return False
    if cat in blob:
        return True
    chars = [ch for ch in cat if not ch.isspace()]
    if not chars:
        return False
    present = sum(1 for ch in chars if ch in blob)
    return present / len(chars) >= min_char_overlap_ratio


def _has_cjk_text(text: str, min_chars: int = 6) -> bool:
    return sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff") >= min_chars


_BAD_SNIPPET_MARKERS = (
    "请登录",
    "免费注册",
    "淘宝网首页",
    "site owner hides",
    "The site owner hides",
)


def _is_usable_product_snippet(text: str) -> bool:
    blob = (text or "").strip()
    if len(blob) < 20 or not _has_cjk_text(blob, min_chars=8):
        return False
    return not any(marker in blob for marker in _BAD_SNIPPET_MARKERS)


def search_product_context_snippets(
    *,
    url: str,
    taobao_item_id: str | None = None,
    jd_item_id: str | None = None,
    max_results_per_query: int = 10,
) -> str:
    """按商品链接或 ID 检索中文商品摘要，供选品池解析回退使用。"""
    queries: list[str] = []
    if taobao_item_id:
        queries.extend(
            [
                f"site:item.taobao.com item.htm id={taobao_item_id}",
                f"site:detail.tmall.com item.htm id={taobao_item_id}",
                f"淘宝 商品 id={taobao_item_id}",
            ]
        )
    if jd_item_id:
        queries.extend(
            [
                f"site:item.jd.com {jd_item_id}",
                f"京东 商品 {jd_item_id}",
            ]
        )
    if url:
        queries.append(url)

    item_id = taobao_item_id or jd_item_id
    collected: list[str] = []

    for query in queries:
        try:
            with DDGS() as ddgs:
                gen = ddgs.text(query, max_results=max_results_per_query)
                if not gen:
                    continue
                for result in gen:
                    title = (result.get("title") or "").strip()
                    body = (result.get("body") or "").strip()
                    href = (result.get("href") or "").strip()
                    blob = f"{title}\n{body}".strip()
                    if not _is_usable_product_snippet(blob):
                        continue
                    if item_id and item_id not in f"{href}\n{blob}":
                        continue
                    collected.append(blob)
                    if len("\n\n".join(collected)) >= 1800:
                        return "\n\n".join(collected[:3])
        except Exception as exc:
            print(f"search_product_context_snippets DDG 失败: {exc}")
            continue

    if collected:
        return "\n\n".join(collected[:3])

    # 最后放宽：仅按 URL 查询时接受任意中文摘要
    if url:
        try:
            with DDGS() as ddgs:
                gen = ddgs.text(url, max_results=max_results_per_query)
                if gen:
                    for result in gen:
                        title = (result.get("title") or "").strip()
                        body = (result.get("body") or "").strip()
                        blob = f"{title}\n{body}".strip()
                        if _is_usable_product_snippet(blob):
                            return blob
        except Exception:
            pass

    return ""


def search_jd_product_price_snippets(
    *,
    title: str = "",
    jd_item_id: str = "",
    max_results_per_query: int = 8,
) -> str:
    """检索京东商品标题/ID 相关摘要，供价格与销量解析回退。"""
    queries: list[str] = []
    if jd_item_id:
        queries.extend(
            [
                f"site:item.jd.com {jd_item_id} 价格",
                f"京东 {jd_item_id} 京东价",
            ]
        )
    cleaned_title = re.sub(r"\s+", " ", (title or "").strip())
    if cleaned_title and len(cleaned_title) >= 6:
        short_title = cleaned_title[:40]
        queries.extend(
            [
                f"{short_title} site:item.jd.com 价格",
                f"{short_title} 京东价 ￥",
            ]
        )

    collected: list[str] = []
    for query in queries:
        try:
            with DDGS() as ddgs:
                gen = ddgs.text(query, max_results=max_results_per_query)
                if not gen:
                    continue
                for result in gen:
                    title_text = (result.get("title") or "").strip()
                    body = (result.get("body") or "").strip()
                    href = (result.get("href") or "").strip()
                    blob = f"{title_text}\n{body}\n{href}".strip()
                    if not _is_usable_product_snippet(blob):
                        continue
                    if jd_item_id and jd_item_id not in blob and "jd.com" not in href:
                        continue
                    if "￥" not in blob and "京东价" not in blob and "条评价" not in blob:
                        continue
                    collected.append(blob)
                    if len("\n\n".join(collected)) >= 1200:
                        return "\n\n".join(collected[:3])
        except Exception as exc:
            print(f"search_jd_product_price_snippets DDG 失败: {exc}")
            continue
    return "\n\n".join(collected[:3]) if collected else ""


def search_taobao_first_item_detail_by_category(
    category: str, max_results_per_query: int = 12
) -> Dict[str, Any] | None:
    """
    按商品类别做外部检索，返回**与该类别文案一致**的一条淘宝系商品详情（非首个 URL 即收）。

    数据来源为 DuckDuckGo 文本结果中的 ``item.taobao.com`` / ``detail.tmall.com`` 商品链；
    在每条结果的标题、摘要上做 ``retrieval_copy_matches_category`` 过滤，取第一条通过的条目。
    若扫描完仍无匹配，返回 ``None``。

    Returns:
        ``category``、``item_id``、``detail_url``、``title``、``summary``（检索摘要）、
        ``matched_from_query``（调试用）；无合适商品时为 ``None``。
    """
    category = (category or "").strip()
    if not category:
        return None

    queries = [
        f"{category} site:item.taobao.com",
        f"{category} site:detail.tmall.com",
    ]
    for q in queries:
        try:
            with DDGS() as ddgs:
                gen = ddgs.text(q, max_results=max_results_per_query)
                if not gen:
                    continue
                for r in gen:
                    href = (r.get("href") or "").strip()
                    if not is_taobao_item_detail_url(href):
                        continue
                    title = (r.get("title") or "").strip()
                    summary = (r.get("body") or "").strip()
                    if not retrieval_copy_matches_category(category, title, summary):
                        continue
                    detail_url = canonical_taobao_item_url(href)
                    item_id = _extract_taobao_item_id(detail_url) or ""
                    return {
                        "category": category,
                        "item_id": item_id,
                        "detail_url": detail_url,
                        "title": title,
                        "summary": summary,
                        "matched_from_query": q,
                    }
        except Exception as e:
            print(f"search_taobao_first_item_detail_by_category DDG 失败: {e}")
            continue
    return None


def _search_duckduckgo_langchain_impl(query: str, site: str = "taobao.com") -> str:
    """同步搜索实现；抛异常时由调用方决定是否重试。"""
    search = DuckDuckGoSearchRun()
    full_query = f"{query} site:{site}"
    result = search.run(full_query)
    return result if result is not None else ""


def search_duckduckgo_langchain(query: str, site: str = "taobao.com"):
    """
    使用 LangChain 的 DuckDuckGoSearchRun 搜索特定网站

    Args:
        query: 搜索查询词
        site: 限定的网站域名

    Returns:
        搜索结果文本
    """
    try:
        return _search_duckduckgo_langchain_impl(query, site)
    except Exception:
        return ""


async def search_duckduckgo_langchain_async(query: str, site: str = "taobao.com") -> str:
    """异步包装 + 可恢复错误重试（指数退避）；最终失败返回空串。"""

    async def once():
        return await asyncio.to_thread(_search_duckduckgo_langchain_impl, query, site)

    try:
        return await retry_with_backoff(
            once,
            max_attempts=settings.SEARCH_HTTP_RETRY_MAX_ATTEMPTS,
            base_delay=settings.SEARCH_HTTP_RETRY_BASE_DELAY,
            max_delay=settings.SEARCH_HTTP_RETRY_MAX_DELAY,
            operation_name="duckduckgo_langchain",
        )
    except Exception:
        return ""


# def get_product_specs(product_name):
#     # 1. 构建精准搜索查询
#     query = f'"{product_name}" 规格参数 site:jd.com OR site:taobao.com'
#     with DDGS() as ddgs:
#         search_results = ddgs.text(query, max_results=3)
#         if not search_results:
#             return None

#         # 2. 获取第一个结果的页面内容
#         target_url = search_results[0]["href"]
#         headers = {
#             "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
#         }
#         try:
#             response = requests.get(target_url, headers=headers, timeout=10)
#             response.raise_for_status()
#         except Exception as e:
#             print(f"请求失败: {e}")
#             return None

#         # 3. 解析HTML，提取参数
#         soup = BeautifulSoup(response.text, "html.parser")
#         # 示例：尝试从JSON-LD中提取
#         json_ld_script = soup.find("script", type="application/ld+json")
#         if json_ld_script:
#             try:
#                 data = json.loads(json_ld_script.string)
#                 return data.get("description", "")  # 假设JSON中包含描述信息
#             except:
#                 pass

#         # 备选方案：提取商品标题和描述
#         title = (
#             soup.find("title").get_text(strip=True) if soup.find("title") else "无标题"
#         )
#         # 使用 .get_text() 提取纯文本并清理
#         description = soup.find("meta", {"name": "description"})
#         description_content = description["content"] if description else "无描述"
#         return {"title": title, "description": description_content}


# def get_product_details_with_selenium(product_url):
#     """
#     使用 Selenium 抓取商品详情页信息

#     Args:
#         product_url: 商品详情页 URL

#     Returns:
#         商品详情信息字典
#     """
#     details = {}

#     try:
#         # 配置 Chrome 浏览器
#         chrome_options = Options()
#         chrome_options.add_argument('--headless')  # 无头模式
#         chrome_options.add_argument('--no-sandbox')
#         chrome_options.add_argument('--disable-dev-shm-usage')
#         chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')

#         # 初始化浏览器
#         driver = webdriver.Chrome(
#             service=Service(ChromeDriverManager().install()),
#             options=chrome_options
#         )

#         # 访问页面，设置页面加载超时
#         driver.set_page_load_timeout(30)  # 页面加载超时30秒
#         driver.set_script_timeout(30)  # 脚本执行超时30秒

#         try:
#             driver.get(product_url)

#             # 等待商品详情标题元素出现（处理动态id的情况）
#             # id格式为: [随机前缀]-SPXQ-title
#             try:
#                 WebDriverWait(driver, 20).until(
#                     EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'quality-life-exposure-placeholder')]"))
#                 )
#                 print("商品详情内容已加载")
#             except TimeoutException:
#                 print("等待商品详情标题超时，继续处理...")

#             # 等待页面加载基本完成
#             WebDriverWait(driver, 10).until(
#                 EC.presence_of_element_located((By.TAG_NAME, 'body'))
#             )

#         except TimeoutException:
#             print("页面加载超时，继续处理已加载内容")

#         # 滚动页面以触发懒加载内容
#         def scroll_page(driver, scroll_pause_time=1, max_scrolls=5):
#             """滚动页面以加载动态内容"""
#             for i in range(max_scrolls):
#                 driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
#                 time.sleep(scroll_pause_time)

#         scroll_page(driver)

#         # 获取页面源码
#         page_source = driver.page_source
#         soup = BeautifulSoup(page_source, 'html.parser')

#         # 提取商品信息
#         # 1. 标题
#         title = soup.find('title')
#         if title:
#             details['title'] = title.get_text(strip=True)

#         # 2. 价格
#         # 淘宝/天猫价格
#         price_ele = soup.find(class_='tm-price') or soup.find(class_='price') or soup.find(class_='J-p-')
#         if price_ele:
#             details['price'] = price_ele.get_text(strip=True)

#         # 3. 商品描述
#         description_meta = soup.find('meta', {'name': 'description'})
#         if description_meta:
#             details['description'] = description_meta.get('content', '')

#         # 4. 规格参数 - 查找包含"商品详情"文本的div附近的规格信息
#         specs = {}
#         # 尝试查找商品详情区域
#         detail_section = soup.find('div', {'id': re.compile(r'.*-title.*')})
#         if detail_section:
#             print(f"找到商品详情区域: {detail_section.get_text()[:100]}")

#         # 京东商品详情页特定处理
#         if 'jd.com' in product_url:
#             # 查找商品详情标签页内容
#             detail_tab = soup.find(class_='tab-con')
#             if detail_tab:
#                 # 查找参数表格
#                 spec_sections = detail_tab.find_all(class_='Ptable')
#                 for section in spec_sections:
#                     # 查找表格行
#                     rows = section.find_all('tr')
#                     for row in rows:
#                         # 京东的参数表格结构
#                         th = row.find('th')
#                         tds = row.find_all('td')
#                         if th and tds:
#                             key = th.get_text(strip=True)
#                             # 有些行有多个 td，取第一个
#                             value = tds[0].get_text(strip=True)
#                             if key and value:
#                                 specs[key] = value
#         else:
#             # 其他网站的通用处理
#             spec_tables = soup.find_all('table', class_=['attributes-list', 'spec-table'])
#             for table in spec_tables:
#                 rows = table.find_all('tr')
#                 for row in rows:
#                     cols = row.find_all(['th', 'td'])
#                     if len(cols) >= 2:
#                         key = cols[0].get_text(strip=True)
#                         value = cols[1].get_text(strip=True)
#                         specs[key] = value

#         # 如果找到了规格参数，添加到详情中
#         if specs:
#             details['specs'] = specs

#         # 5. 商品图片
#         images = []
#         img_tags = soup.find_all('img')
#         for img in img_tags:
#             img_url = img.get('src') or img.get('data-src')
#             if img_url and 'http' in img_url:
#                 images.append(img_url)
#         if images:
#             details['images'] = images[:5]  # 只保存前5张图片

#         # 6. 商品ID
#         if 'taobao.com' in product_url or 'tmall.com' in product_url:
#             product_id_match = re.search(r'id=(\d+)', product_url)
#             if product_id_match:
#                 details['product_id'] = product_id_match.group(1)
#         elif 'jd.com' in product_url:
#             product_id_match = re.search(r'/\d+\.html', product_url)
#             if product_id_match:
#                 details['product_id'] = product_id_match.group(0).strip('/.html')

#         # 7. URL信息
#         details['url'] = product_url

#         # 关闭浏览器
#         driver.quit()

#     except Exception as e:
#         print(f"Selenium 抓取出错: {str(e)}")
#         if 'driver' in locals():
#             driver.quit()

#     return details

if __name__ == "__main__":
    # 测试搜索功能
    query = "按摩器"
    print(f"搜索: {query}")

    # 测试文本搜索
    print("\n文本搜索结果:")
    text_results = search_duckduckgo(query, 2, "www.taobao.com")
    for i, result in enumerate(text_results):
        print(f"{i + 1}. {result['title']}")
        print(f"   URL: {result['url']}")
        print(f"   摘要: {result['snippet'][:100]}...")

    # # 测试新闻搜索
    # print("\n新闻搜索结果:")
    # news_results = search_news(query)
    # for i, result in enumerate(news_results):
    #     print(f"{i+1}. {result['title']}")
    #     print(f"   URL: {result['url']}")
    #     print(f"   日期: {result['date']}")

    # # 测试图片搜索
    # print("\n图片搜索结果:")
    # image_results = search_images(query)
    # for i, result in enumerate(image_results):
    #     print(f"{i+1}. {result['title']}")
    #     print(f"   图片URL: {result['image_url']}")
    #     print(f"   来源URL: {result['source_url']}")

    # 测试 LangChain 搜索
    # print("\nLangChain 搜索结果 (淘宝):")
    # langchain_result = search_duckduckgo_langchain("运动鞋 男")
    # print(langchain_result)
