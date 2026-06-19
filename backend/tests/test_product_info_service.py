import asyncio
import os
import sys
from pathlib import Path

import pandas as pd
import pytest
from dotenv import load_dotenv

project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.agents.product_rag_system.agent import ProductRagAgent
from app.agents.product_rag_system.product_database import (
    CSV_CORE_COLUMNS,
    SEARCH_TEXT_MAX_TOKENS,
    ProductDatabase,
    default_product_data_dir,
)
from app.agents.product_rag_system.product_scrape_database import (
    SCRAPE_RECORD_COLUMNS,
    ProductScrapeDatabase,
)
from app.services.product_info_service import (
    ProductInfoService,
    PreparedProduct,
    _EXTRACT_PROMPT,
    _extract_jd_item_id,
    _normalize_optional_url,
    _preview_comments,
    _preview_cover_image,
    _resolve_product_name,
    _validate_extracted_product_fields,
    build_scrape_payload,
    compose_product_context,
    prepared_product_to_item,
    product_record_to_item,
    resolve_product_url,
    validate_product_url,
    ProductGatherResult,
)
from app.services.product_page_scraper import (
    ProductPageCapture,
    _normalize_jd_comment_items,
    _parse_jd_comments_response,
    _parse_jd_document_title,
    _parse_jd_mgets_payload,
    _parse_numeric_price,
    _parse_price_from_visible_text,
    _parse_sales_from_visible_text,
    is_jd_blocked_page,
    is_playwright_available,
    is_usable_product_page_text,
    playwright_setup_hint,
    save_product_screenshot,
    screenshot_local_path,
)
from app.utils.token_counter import token_counter

load_dotenv()

JD_E2E_URL = (
    "https://item.jd.com/100045686996.html"
    "?sourceType=m-activity&bbtf=1&pageId=6265621"
)


def _e2e_data_dir(tmp_path: Path) -> Path:
    """默认写入项目 data 目录便于查看；PRODUCT_E2E_USE_TMP=1 时用 pytest 临时目录。"""
    if os.environ.get("PRODUCT_E2E_USE_TMP", "").strip().lower() in {"1", "true", "yes"}:
        print("[E2E] 使用 pytest 临时目录 (PRODUCT_E2E_USE_TMP=1)")
        return tmp_path

    override = os.environ.get("PRODUCT_E2E_DATA_DIR", "").strip()
    if override:
        directory = Path(override).expanduser().resolve()
    else:
        directory = Path(default_product_data_dir())

    directory.mkdir(parents=True, exist_ok=True)
    print(f"[E2E] CSV 将保存到: {directory}")
    return directory


def test_build_search_text_respects_token_limit():
    long_description = "按摩" * 800
    text = ProductDatabase.build_search_text(
        "妙界按摩仪",
        "个护",
        long_description,
        "妙界旗舰店",
        max_tokens=512,
    )
    assert token_counter.count_tokens(text) <= 512
    assert "妙界按摩仪" in text


def test_validate_product_url_accepts_supported_hosts():
    url = validate_product_url("https://item.taobao.com/item.htm?id=123456")
    assert url.startswith("https://item.taobao.com")


def test_validate_product_url_rejects_unsupported_host():
    with pytest.raises(ValueError, match="暂仅支持"):
        validate_product_url("https://example.com/product/1")


def test_validate_product_url_accepts_short_link_host():
    url = validate_product_url("https://e.tb.cn/h.xxxxx")
    assert url.startswith("https://e.tb.cn")


def test_extract_jd_item_id_from_url():
    assert _extract_jd_item_id("https://item.jd.com/100012043978.html") == "100012043978"


def test_parse_jd_document_title():
    assert _parse_jd_document_title("米家智能除湿机 22L - 京东") == "米家智能除湿机 22L"
    assert _parse_jd_document_title("  请登录 - 京东  ") == ""
    assert _parse_jd_document_title("") == ""


def test_is_jd_blocked_page():
    assert is_jd_blocked_page("https://pc-frequent-pro.pf.jd.com/?from=pc_item&reason=403")
    assert is_jd_blocked_page("https://item.jd.com/1.html", title="PC频控页")
    assert not is_jd_blocked_page("https://item.jd.com/1.html", title="华为FreeBuds 5i")


def test_resolve_jd_url_keeps_item_id_from_query_params():
    normalized = asyncio.run(resolve_product_url(JD_E2E_URL))
    assert normalized == "https://item.jd.com/100045686996.html"


def test_validate_extracted_product_fields_rejects_placeholder_name():
    with pytest.raises(ValueError, match="未能识别有效商品名称"):
        _validate_extracted_product_fields(
            {
                "name": "未知商品",
                "description": "无法从页面文本中提取有效商品信息。",
            }
        )


def test_resolve_product_name_uses_capture_title_as_fallback():
    capture = ProductPageCapture(final_url="https://item.jd.com/1.html", title="米家智能除湿机 22L")
    name = _resolve_product_name("未知商品", capture)
    assert name == "米家智能除湿机 22L"


def test_resolve_product_name_keeps_valid_llm_name():
    capture = ProductPageCapture(final_url="https://item.jd.com/1.html", title="米家智能除湿机 22L")
    name = _resolve_product_name("小米米家除湿机", capture)
    assert name == "小米米家除湿机"


def test_normalize_optional_url_handles_nan():
    assert _normalize_optional_url(float("nan")) is None
    assert _normalize_optional_url("") is None
    assert _normalize_optional_url("https://item.jd.com/1.html") == "https://item.jd.com/1.html"


def test_product_record_to_item_handles_empty_url():
    import math

    item = product_record_to_item(
        {
            "id": 1,
            "name": "测试",
            "category": "数码",
            "price": 99,
            "description": "描述",
            "sales": 1,
            "shop_name": "店",
            "url": float("nan"),
            "search_text": "测试 数码 描述 店",
        }
    )
    assert item.url is None


def test_is_usable_product_page_text_allows_jd_detail_with_footer_slogan():
    assert is_usable_product_page_text(
        "京东(JD.COM)-正品低价、品质保障 " * 5 + " 其他导航内容",
        product_title="华为 Mate 60 Pro 手机",
        min_chars=80,
    )


def test_is_usable_product_page_text_blocks_jd_homepage():
    homepage = "京东(JD.COM)-正品低价、品质保障、配送及时、轻松购物！"
    assert not is_usable_product_page_text(homepage, min_chars=40)


def test_extract_prompt_renders_json_example_without_key_error():
    rendered = _EXTRACT_PROMPT.format(
        url="https://item.jd.com/1.html",
        page_text="示例商品文本",
    )
    assert '{"name": ""}' in rendered
    assert "示例商品文本" in rendered


def test_playwright_setup_hint_is_documented():
    hint = playwright_setup_hint()
    assert "python3 -m pip install playwright" in hint
    assert "python3 -m playwright install chromium" in hint
    assert isinstance(is_playwright_available(), bool)


def test_compose_product_context_merges_sources():
    context = compose_product_context(
        url="https://item.taobao.com/item.htm?id=1",
        page_text="妙界按摩仪",
        vision_text="图片识别：肩颈按摩、热敷",
        search_text="淘宝检索摘要",
        price=199.0,
        sales=12000,
    )
    assert "页面文本" in context
    assert "图片识别补充" in context
    assert "检索补充" in context
    assert "页面价格：199" in context
    assert "页面销量：12000" in context
    assert "妙界按摩仪" in context


def test_parse_price_and_sales_from_visible_text():
    text = "亚朵星球枕头 京东价：￥159.00 50万+条评价"
    assert _parse_price_from_visible_text(text) == 159.0
    assert _parse_sales_from_visible_text(text) == 500000


def test_parse_price_from_jd_product_price_value():
    assert _parse_numeric_price("159") == 159.0
    assert _parse_numeric_price("159.00") == 159.0
    assert _parse_numeric_price("￥159.00") == 159.0


def test_parse_jd_mgets_payload():
    assert _parse_jd_mgets_payload([{"p": "159.00", "op": "199.00"}]) == 159.0
    assert _parse_jd_mgets_payload([{"op": "199.00"}]) == 199.0
    assert _parse_jd_mgets_payload([]) is None
    assert _parse_jd_mgets_payload({}) is None


def test_is_valid_jd_price_text_rejects_masked():
    from app.services.product_page_scraper import _is_valid_jd_price_text

    assert _is_valid_jd_price_text("159") is True
    assert _is_valid_jd_price_text("¥159.00") is True
    assert _is_valid_jd_price_text("1??") is False
    assert _is_valid_jd_price_text("登录查看价格") is False


def test_parse_jd_ware_business_payload():
    from app.services.product_page_scraper import _parse_jd_ware_business_payload

    payload = {
        "price": {"p": "299.00", "jdPrice": "299.00"},
        "comment": {"commentCountStr": "1.2万+"},
    }
    price, sales = _parse_jd_ware_business_payload(payload)
    assert price == 299.0
    assert sales == 12000


def test_enrich_capture_price_sales_uses_prefetched():
    from app.services.product_page_scraper import _enrich_capture_price_sales

    async def _run() -> None:
        capture = ProductPageCapture(
            final_url="https://item.jd.com/100045686996.html",
            visible_text="亚朵星球枕头",
            platform="jd",
        )
        await _enrich_capture_price_sales(
            capture,
            "https://item.jd.com/100045686996.html",
            "jd",
            page=None,
            prefetched_price=159.0,
            prefetched_sales=500000,
        )
        assert capture.price == 159.0
        assert capture.sales == 500000

    asyncio.run(_run())


def test_normalize_jd_comment_items_limits_to_ten():
    raw = [
        {
            "content": f"评论{i}",
            "nickname": f"用户{i}",
            "score": 5,
            "creationTime": "2026-01-01",
        }
        for i in range(15)
    ]
    comments = _normalize_jd_comment_items(raw, limit=10)
    assert len(comments) == 10
    assert comments[0]["content"] == "评论0"
    assert comments[0]["nickname"] == "用户0"


def test_parse_jd_comments_response_from_jsonp():
    body = 'fetchJSON_comment98({"comments":[{"content":"枕头很软","nickname":"jd用户","score":5,"creationTime":"2026-01-01"}]})'
    comments, status = _parse_jd_comments_response(body, limit=10)
    assert len(comments) == 1
    assert comments[0]["content"] == "枕头很软"
    assert status == "ok"


def test_parse_jd_comments_response_detects_api_blocked():
    comments, status = _parse_jd_comments_response("系统繁忙", limit=10)
    assert comments == []
    assert status == "api_blocked"


def test_parse_jd_comments_response_detects_gbk_mojibake_busy():
    comments, status = _parse_jd_comments_response("绯荤粺绻佸繖", limit=10)
    assert comments == []
    assert status == "api_blocked"


def test_save_product_screenshot_returns_url_not_base64(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.services.product_page_scraper.get_product_screenshot_dir",
        lambda: tmp_path,
    )
    url = save_product_screenshot(
        b"fake-jpeg-bytes",
        platform="jd",
        url="https://item.jd.com/100045686996.html",
    )
    assert url == "/product-screenshots/jd_100045686996.jpg"
    assert (tmp_path / "jd_100045686996.jpg").read_bytes() == b"fake-jpeg-bytes"
    assert screenshot_local_path(url) == tmp_path / "jd_100045686996.jpg"


def test_build_scrape_payload_persists_capture_fields():
    capture = ProductPageCapture(
        final_url="https://item.jd.com/100045686996.html",
        visible_text="页面正文",
        title="亚朵星球枕头",
        screenshot_url="/product-screenshots/jd_100045686996.jpg",
        detail_image_urls=["https://img.example/a.jpg", "https://img.example/b.jpg"],
        source="playwright",
        platform="jd",
        price_text="￥159",
        shop="亚朵星球京东自营旗舰店",
        price=159.0,
        sales=500000,
    )
    gather = ProductGatherResult(
        context="上下文",
        capture=capture,
        page_text="页面正文",
        vision_text="视觉摘要",
        search_text="检索摘要",
    )
    payload = build_scrape_payload("https://item.jd.com/100045686996.html", gather)
    assert payload["scrape_title"] == "亚朵星球枕头"
    assert payload["scrape_platform"] == "jd"
    assert payload["scrape_price"] == 159.0
    assert payload["scrape_sales"] == 500000
    assert payload["scrape_shop"] == "亚朵星球京东自营旗舰店"
    assert payload["scrape_screenshot_url"] == "/product-screenshots/jd_100045686996.jpg"
    assert payload["comments_list"] == []
    assert payload["scrape_comments_status"] == ""
    assert "img.example/a.jpg" in payload["scrape_detail_images"]


def test_prepared_product_to_item_includes_cover_image_and_top_comments():
    capture = ProductPageCapture(
        final_url="https://item.jd.com/100045686996.html",
        head_image_url="https://img.example/head.jpg",
        detail_image_urls=[
            "https://img.example/a.jpg",
            "https://img.example/b.jpg",
        ],
        comments_list=[
            {"content": "评论一", "nickname": "用户A", "score": "5", "creation_time": "2025-01-01"},
            {"content": "评论二", "nickname": "用户B", "score": "4", "creation_time": "2025-01-02"},
            {"content": "评论三", "nickname": "用户C", "score": "5", "creation_time": "2025-01-03"},
            {"content": "评论四", "nickname": "用户D", "score": "3", "creation_time": "2025-01-04"},
        ],
    )
    gather = ProductGatherResult(context="上下文", capture=capture)
    prepared = PreparedProduct(
        normalized_url="https://item.jd.com/100045686996.html",
        fields={
            "name": "亚朵星球枕头",
            "category": "家居",
            "description": "柔软支撑",
            "shop_name": "亚朵星球旗舰店",
            "price": 159.0,
            "sales": 500000,
        },
        gather=gather,
        search_text="亚朵星球枕头 家居",
    )

    assert _preview_cover_image(prepared) == "https://img.example/head.jpg"
    assert len(_preview_comments(prepared)) == 3
    assert _preview_comments(prepared)[0].content == "评论一"

    item = prepared_product_to_item(prepared)
    assert item.cover_image == "https://img.example/head.jpg"
    assert len(item.comments) == 3
    assert item.comments[2].nickname == "用户C"


def test_list_products_returns_newest_first(tmp_path):
    csv_path = tmp_path / "products.csv"
    csv_path.write_text(
        "id,name,category,price,description,sales,shop_name,url\n"
        "1,旧商品,数码,99,描述,10,老店,\n"
        "2,新商品,家电,199,描述,20,新店,https://item.jd.com/2.html\n",
        encoding="utf-8",
    )
    from app.agents.product_rag_system.agent import ProductRagAgent

    rag_agent = ProductRagAgent(data_path=str(csv_path))
    service = ProductInfoService(rag_agent)
    response = service.list_products()
    assert [item.id for item in response.items] == ["2", "1"]


def test_get_product_includes_scrape_cover_and_comments(tmp_path):
    products_csv = tmp_path / "products.csv"
    products_csv.write_text(
        "id,name,category,price,description,sales,shop_name,url\n"
        "1,测试商品,数码,99,描述,10,测试店,https://item.jd.com/1.html\n",
        encoding="utf-8",
    )
    scrape_csv = tmp_path / "scraped_products.csv"
    scrape_csv.write_text(
        "id,product_id,url,name,category,price,description,sales,shop_name,search_text,"
        "scrape_title,scrape_platform,scrape_source,scrape_final_url,scrape_price,scrape_sales,"
        "scrape_shop,scrape_price_text,scrape_visible_text,scrape_vision_text,scrape_search_text,"
        "scrape_detail_images,scrape_screenshot_url,comments_list,scrape_comments_status,scraped_at\n"
        '1,1,https://item.jd.com/1.html,测试商品,数码,99,描述,10,测试店,search,title,jd,playwright,'
        'https://item.jd.com/1.html,,,,,,,,https://img.example/head.jpg|https://img.example/detail.jpg,'
        '/product-screenshots/jd_1.jpg,"[{""content"": ""很好用"", ""nickname"": ""买家A""}]",ok,2026-01-01T00:00:00+00:00\n',
        encoding="utf-8",
    )
    from app.agents.product_rag_system.agent import ProductRagAgent

    rag_agent = ProductRagAgent(data_path=str(products_csv))
    rag_agent.scrape_db = ProductScrapeDatabase(data_path=str(scrape_csv))
    service = ProductInfoService(rag_agent)

    product = service.get_product("1")
    assert product is not None
    assert product.cover_image == "https://img.example/head.jpg"
    assert len(product.comments) == 1
    assert product.comments[0].content == "很好用"


def test_product_database_add_and_delete(tmp_path):
    csv_path = tmp_path / "products.csv"
    csv_path.write_text(
        "id,name,category,price,description,sales,shop_name\n"
        "1,测试商品,数码,99,描述,10,测试店\n",
        encoding="utf-8",
    )
    db = ProductDatabase(str(csv_path))

    record = db.add_product(
        {
            "name": "新增商品",
            "category": "家电",
            "price": 199,
            "description": "便携好用",
            "sales": 20,
            "shop_name": "新店铺",
            "url": "https://item.taobao.com/item.htm?id=999",
        }
    )
    assert record["id"] == 2
    assert token_counter.count_tokens(record["search_text"]) <= 512
    assert len(db.get_all_products()) == 2

    assert db.delete_product("2") is True
    assert len(db.get_all_products()) == 1


def test_add_product_rewrites_csv_without_corrupting_rows(tmp_path):
    csv_path = tmp_path / "products.csv"
    csv_path.write_text(
        "id,name,category,price,description,sales,shop_name,url\n"
        "1,测试商品,数码,99,描述,10,测试店,\n",
        encoding="utf-8",
    )
    db = ProductDatabase(str(csv_path))
    db.add_product(
        {
            "name": "逗号，测试商品",
            "category": "家电",
            "price": 199,
            "description": "支持，多字段，写入",
            "sales": 20,
            "shop_name": "新店铺",
            "url": "https://item.jd.com/100045686996.html",
        }
    )

    reloaded = ProductDatabase(str(csv_path))
    assert len(reloaded.get_all_products()) == 2
    assert reloaded.get_product_by_id("2")["name"] == "逗号，测试商品"
    assert list(pd.read_csv(csv_path).columns) == CSV_CORE_COLUMNS


def test_add_product_persists_scrape_columns(tmp_path):
    products_csv = tmp_path / "products.csv"
    products_csv.write_text(
        "id,name,category,price,description,sales,shop_name,url\n"
        "1,测试商品,数码,99,描述,10,测试店,\n",
        encoding="utf-8",
    )
    db = ProductDatabase(str(products_csv))
    db.add_product(
        {
            "name": "爬虫商品",
            "category": "记忆枕",
            "price": 159,
            "description": "慢回弹",
            "sales": 500000,
            "shop_name": "亚朵旗舰店",
            "url": "https://item.jd.com/100045686996.html",
            "search_text": "爬虫商品 记忆枕",
        }
    )

    scrape_db = ProductScrapeDatabase(products_csv_path=str(products_csv))
    scrape_db.add_scrape_record(
        product_id=2,
        url="https://item.jd.com/100045686996.html",
        product_fields={
            "name": "爬虫商品",
            "category": "记忆枕",
            "price": 159,
            "description": "慢回弹",
            "sales": 500000,
            "shop_name": "亚朵旗舰店",
        },
        scrape_payload={
            "scrape_title": "亚朵星球枕头",
            "scrape_platform": "jd",
            "scrape_source": "playwright",
            "scrape_final_url": "https://item.jd.com/100045686996.html",
            "scrape_price": 159.0,
            "scrape_sales": 500000,
            "scrape_shop": "亚朵旗舰店",
            "scrape_price_text": "￥159",
            "scrape_visible_text": "页面可见文本",
            "scrape_vision_text": "视觉识别文本",
            "scrape_search_text": "",
            "scrape_detail_images": "https://img.example/a.jpg|https://img.example/b.jpg",
            "scrape_screenshot_url": "/product-screenshots/jd_100045686996.jpg",
            "comments_list": [
                {"content": "枕头很软", "nickname": "jd用户", "score": "5", "creation_time": "2026-01-01"},
            ],
        },
        search_text="爬虫商品 记忆枕",
    )

    products_df = pd.read_csv(products_csv)
    scrape_df = pd.read_csv(scrape_db.data_path)
    assert list(products_df.columns) == CSV_CORE_COLUMNS
    assert list(scrape_df.columns) == SCRAPE_RECORD_COLUMNS
    row = scrape_df.iloc[0]
    assert row["scrape_title"] == "亚朵星球枕头"
    assert row["scrape_platform"] == "jd"
    assert float(row["scrape_price"]) == 159.0
    assert int(row["scrape_sales"]) == 500000
    assert "img.example/a.jpg" in str(row["scrape_detail_images"])
    assert row["scrape_screenshot_url"] == "/product-screenshots/jd_100045686996.jpg"
    assert int(row["product_id"]) == 2
    assert "枕头很软" in str(row["comments_list"])


async def _run_jd_product_info_e2e(tmp_path: Path) -> None:
    """端到端：京东商品链接 → 解析 → 抓取/识图 → 结构化 → 入库。"""
    normalized_url = await resolve_product_url(JD_E2E_URL)
    assert "item.jd.com" in normalized_url
    assert _extract_jd_item_id(normalized_url) == "100045686996"

    csv_path = _e2e_data_dir(tmp_path) / "e2e_products.csv"
    csv_path.write_text(
        "id,name,category,price,description,sales,shop_name\n",
        encoding="utf-8",
    )
    rag_agent = ProductRagAgent(str(csv_path))
    print(f"[E2E] products_csv={rag_agent.products_db.data_path}")
    print(f"[E2E] scrape_csv={rag_agent.scrape_db.data_path}")

    async def _noop_index_ready() -> None:
        return None

    rag_agent.ensure_index_ready = _noop_index_ready  # type: ignore[method-assign]
    rag_agent.add_product_to_index = lambda _product: None  # type: ignore[method-assign]

    service = ProductInfoService(rag_agent)
    result = await service.create_from_url(JD_E2E_URL)
    print(result)

    product = result.product
    assert product.id
    assert product.name.strip()
    assert product.category.strip()
    assert product.shop_name.strip()
    assert (product.url or "").startswith("http")
    assert len(rag_agent.products_db.get_all_products()) == 1

    stored = rag_agent.products_db.get_all_products()[0]
    search_text = stored["search_text"]
    assert token_counter.count_tokens(search_text) <= SEARCH_TEXT_MAX_TOKENS

    scrape_stored = rag_agent.scrape_db.get_by_product_id(product.id)
    assert scrape_stored is not None
    assert scrape_stored["scrape_title"]
    assert scrape_stored["scrape_platform"] == "jd"
    assert scrape_stored["scrape_visible_text"]
    assert str(scrape_stored["scrape_screenshot_url"]).startswith("/product-screenshots/")
    assert Path(rag_agent.scrape_db.data_path).is_file()
    print(f"[E2E] 已生成 scraped_products.csv: {rag_agent.scrape_db.data_path}")


@pytest.mark.network
@pytest.mark.integration
def test_jd_url_full_product_info_pipeline(tmp_path):
    asyncio.run(_run_jd_product_info_e2e(tmp_path))
