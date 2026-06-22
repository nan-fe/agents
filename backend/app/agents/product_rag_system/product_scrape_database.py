"""爬虫原始记录 CSV：与选品池 taobao_products.csv 分离存储。

说明：本文件是“识别后的原始抓取数据存储文件”，用于保存头图、评论、页面可见文本等抓取明细。
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from typing import Any

import pandas as pd

from .product_database import default_product_data_dir

SCRAPE_TEXT_MAX_CHARS = 8000
DETAIL_IMAGE_SEPARATOR = "|"
DEFAULT_SCRAPE_FILENAME = "scraped_products.csv"

# 结构化字段 + 爬虫原始字段
SCRAPE_RECORD_COLUMNS = [
    "id",
    "product_id",
    "url",
    "name",
    "category",
    "price",
    "description",
    "sales",
    "shop_name",
    "search_text",
    "scrape_title",
    "scrape_platform",
    "scrape_source",
    "scrape_final_url",
    "scrape_price",
    "scrape_sales",
    "scrape_shop",
    "scrape_price_text",
    "scrape_visible_text",
    "scrape_vision_text",
    "scrape_search_text",
    "scrape_detail_images",
    "scrape_screenshot_url",
    "comments_list",
    "scrape_comments_status",
    "scraped_at",
]


def default_scrape_data_path(products_csv_path: str | None = None) -> str:
    if products_csv_path:
        return os.path.join(os.path.dirname(products_csv_path), DEFAULT_SCRAPE_FILENAME)
    return os.path.join(default_product_data_dir(), DEFAULT_SCRAPE_FILENAME)


class ProductScrapeDatabase:
    """商品爬虫记录库（识别后的原始抓取数据，独立 CSV）。"""

    def __init__(self, data_path: str | None = None, products_csv_path: str | None = None):
        self.data_path = data_path or default_scrape_data_path(products_csv_path)
        self.records: list[dict[str, Any]] = []
        self._ensure_data_file()
        self._load_data()

    def _ensure_data_file(self) -> None:
        if os.path.exists(self.data_path):
            print(f"已加载爬虫记录文件: {self.data_path}")
            return
        os.makedirs(os.path.dirname(self.data_path), exist_ok=True)
        pd.DataFrame(columns=SCRAPE_RECORD_COLUMNS).to_csv(
            self.data_path,
            index=False,
            encoding="utf-8",
        )
        print(f"已创建爬虫记录文件: {self.data_path}")

    def _load_data(self) -> None:
        df = pd.read_csv(self.data_path)
        for column in SCRAPE_RECORD_COLUMNS:
            if column not in df.columns:
                df[column] = ""
        df = df[SCRAPE_RECORD_COLUMNS]

        if len(df):
            df["id"] = df["id"].astype(str).str.strip()
            df["product_id"] = df["product_id"].astype(str).str.strip()

        text_columns = [
            col
            for col in SCRAPE_RECORD_COLUMNS
            if col not in {"id", "product_id", "price", "sales", "scrape_price", "scrape_sales"}
        ]
        for col in text_columns:
            df[col] = df[col].fillna("").astype(str).str.strip()

        self.records = df.to_dict(orient="records")
        print(f"成功加载 {len(self.records)} 条爬虫记录")

    def _next_scrape_id(self) -> int:
        if not self.records:
            return 1
        numeric_ids = []
        for record in self.records:
            try:
                numeric_ids.append(int(record["id"]))
            except (TypeError, ValueError):
                continue
        return max(numeric_ids, default=0) + 1

    @staticmethod
    def _optional_float(value: Any) -> float | None:
        if value is None or value == "":
            return None
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None
        return parsed if parsed > 0 else None

    @staticmethod
    def _optional_int(value: Any) -> int | None:
        if value is None or value == "":
            return None
        try:
            parsed = int(float(value))
        except (TypeError, ValueError):
            return None
        return parsed if parsed > 0 else None

    @staticmethod
    def _truncate_text(value: Any, max_chars: int = SCRAPE_TEXT_MAX_CHARS) -> str:
        text = str(value or "").strip()
        if len(text) <= max_chars:
            return text
        return text[:max_chars]

    @staticmethod
    def _serialize_comments_list(value: Any) -> str:
        if value is None or value == "":
            return ""
        if isinstance(value, str):
            return value.strip()
        try:
            return json.dumps(value, ensure_ascii=False)
        except (TypeError, ValueError):
            return str(value).strip()

    def add_scrape_record(
        self,
        *,
        product_id: int | str,
        url: str,
        product_fields: dict[str, Any],
        scrape_payload: dict[str, Any],
        search_text: str = "",
    ) -> dict[str, Any]:
        """追加一条爬虫记录，并关联选品池 product_id。"""
        record = {
            "id": self._next_scrape_id(),
            "product_id": int(product_id),
            "url": str(url or "").strip(),
            "name": str(product_fields.get("name", "")).strip(),
            "category": str(product_fields.get("category", "")).strip(),
            "price": float(product_fields.get("price", 0) or 0),
            "description": str(product_fields.get("description", "")).strip(),
            "sales": int(product_fields.get("sales", 0) or 0),
            "shop_name": str(product_fields.get("shop_name", "")).strip(),
            "search_text": str(search_text or "").strip(),
            "scrape_title": str(scrape_payload.get("scrape_title", "")).strip(),
            "scrape_platform": str(scrape_payload.get("scrape_platform", "")).strip(),
            "scrape_source": str(scrape_payload.get("scrape_source", "")).strip(),
            "scrape_final_url": str(scrape_payload.get("scrape_final_url", "")).strip(),
            "scrape_price": self._optional_float(scrape_payload.get("scrape_price")),
            "scrape_sales": self._optional_int(scrape_payload.get("scrape_sales")),
            "scrape_shop": str(scrape_payload.get("scrape_shop", "")).strip(),
            "scrape_price_text": str(scrape_payload.get("scrape_price_text", "")).strip(),
            "scrape_visible_text": self._truncate_text(
                scrape_payload.get("scrape_visible_text", "")
            ),
            "scrape_vision_text": self._truncate_text(scrape_payload.get("scrape_vision_text", "")),
            "scrape_search_text": self._truncate_text(scrape_payload.get("scrape_search_text", "")),
            "scrape_detail_images": str(scrape_payload.get("scrape_detail_images", "")).strip(),
            "scrape_screenshot_url": str(scrape_payload.get("scrape_screenshot_url", "")).strip(),
            "comments_list": self._serialize_comments_list(scrape_payload.get("comments_list")),
            "scrape_comments_status": str(scrape_payload.get("scrape_comments_status", "")).strip(),
            "scraped_at": datetime.now(UTC).isoformat(),
        }
        self.records.append(record)
        self._rewrite_csv()
        print(
            f"[ProductScrapeDatabase] 已写入爬虫记录 scrape_id={record['id']} "
            f"product_id={record['product_id']} path={self.data_path}"
        )
        return record

    def get_by_product_id(self, product_id: str | int) -> dict[str, Any] | None:
        target = str(product_id)
        for record in self.records:
            if str(record.get("product_id")) == target:
                return record
        return None

    def delete_by_product_id(self, product_id: str | int) -> bool:
        target = str(product_id)
        before = len(self.records)
        self.records = [
            record for record in self.records if str(record.get("product_id")) != target
        ]
        if len(self.records) == before:
            return False
        self._rewrite_csv()
        return True

    def _rewrite_csv(self) -> None:
        rows: list[dict[str, Any]] = []
        for record in self.records:
            row: dict[str, Any] = {}
            for column in SCRAPE_RECORD_COLUMNS:
                value = record.get(column, "")
                if value is None:
                    value = ""
                row[column] = value
            rows.append(row)
        pd.DataFrame(rows, columns=SCRAPE_RECORD_COLUMNS).to_csv(
            self.data_path,
            index=False,
            encoding="utf-8",
        )
