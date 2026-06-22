"""
产品数据库模块 - 管理商品数据的加载、清洗和存储
"""

import os
import re
from typing import Any, Dict, List

import pandas as pd

from app.utils.token_counter import token_counter

SEARCH_TEXT_MAX_TOKENS = 512

CSV_CORE_COLUMNS = [
    "id",
    "name",
    "category",
    "price",
    "description",
    "sales",
    "shop_name",
    "url",
]

DEFAULT_PRODUCTS_FILENAME = "taobao_products.csv"


def default_product_data_dir() -> str:
    """选品池与爬虫 CSV 的默认目录（可持久查看）。"""
    module_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(module_dir, "data")


def default_products_csv_path() -> str:
    return os.path.join(default_product_data_dir(), DEFAULT_PRODUCTS_FILENAME)


class ProductDatabase:
    """商品数据库类（选品池 / RAG 索引，不含爬虫原始字段）。"""

    def __init__(self, data_path: str = None):
        if data_path is None:
            data_path = default_products_csv_path()

        self.data_path = data_path
        self.products_data = []
        self.corpus = []

        self._ensure_data_file()
        self._load_data()

    def _ensure_data_file(self):
        """确保数据文件存在，若不存在则创建示例数据"""
        if not os.path.exists(self.data_path):
            os.makedirs(os.path.dirname(self.data_path), exist_ok=True)
            with open(self.data_path, "w", encoding="utf-8") as f:
                sample_data = """id,name,category,price,description,sales,shop_name,url
1,真无线降噪蓝牙耳机,数码,199,蓝牙5.3，主动降噪，30小时续航，IPX7防水,5200,小米官方旗舰店,
2,2024夏季纯棉T恤男,男装,49.9,100%纯棉，多色可选，透气亲肤，简约百搭,3400,优衣库官方店
3,苹果iPhone15 Pro,手机,7999,A17 Pro芯片，钛金属边框，4800万像素，灵动岛,1890,Apple官方旗舰店
4,家用全自动咖啡机,家电,899,20bar高压萃取，一键卡布奇诺，可拆卸水箱,2100,德龙电器旗舰店
5,运动跑步鞋女,女鞋,159,网面透气，轻便缓震，防滑耐磨，多色可选,6700,安踏官方店
6,大容量充电宝20000mAh,数码,89,双向快充，数显电量，可上飞机，轻薄便携,9800,罗马仕旗舰店
7,儿童积木玩具益智,母婴,129,大颗粒积木，环保材质，兼容乐高，培养创造力,3100,乐高官方旗舰店
8,不锈钢不粘锅炒锅,厨具,79,无涂层，轻烟不粘，燃气电磁炉通用,4200,苏泊尔官方店
9,男士电动剃须刀,个护,159,浮动三刀头，Type-C充电，全身水洗，续航60分钟,5600,飞科官方旗舰店
10,便携折叠户外桌椅,运动户外,129,铝合金桌面，牛津布椅，承重150kg，收纳方便,1950,探险者户外旗舰店
11,妙界R3至尊版肩颈按摩仪,个护,404,揉捏脖子腰背部颈椎按摩器斜方肌热敷披肩,1950,妙界旗舰店,"""
                f.write(sample_data)
            print(f"已自动创建示例数据文件: {self.data_path}")
        else:
            print(f"已加载数据文件: {self.data_path}")

    def _load_data(self):
        """加载CSV数据并进行清洗"""
        df = pd.read_csv(self.data_path)

        for column in CSV_CORE_COLUMNS:
            if column not in df.columns:
                df[column] = ""

        df = df[CSV_CORE_COLUMNS]

        # 去除 ID 列的空格并转换为整数
        df["id"] = df["id"].astype(str).str.strip().astype(int)

        df["url"] = df["url"].fillna("")

        for col in ["name", "category", "description", "shop_name", "url"]:
            if col in df.columns:
                df[col] = df[col].fillna("").astype(str).str.strip()
                if col == "url":
                    df[col] = df[col].replace("nan", "")

        df["search_text"] = df.apply(
            lambda row: (
                f"{row['name']} {row['category']} {row['description']} {row['shop_name']}".strip()
            ),
            axis=1,
        )

        self.products_data = df.to_dict(orient="records")
        self.corpus = df["search_text"].tolist()

        print(f"成功加载 {len(self.products_data)} 条商品数据")

    def get_all_products(self) -> List[Dict]:
        """获取所有商品数据"""
        return self.products_data

    def get_product_by_id(self, product_id: str) -> Dict | None:
        """根据ID获取单个商品"""
        for product in self.products_data:
            if str(product["id"]) == str(product_id):
                return product
        return None

    def get_corpus(self) -> List[str]:
        """获取所有商品的搜索文本（用于BM25）"""
        return self.corpus

    def get_metadata(self) -> List[Dict]:
        """获取元数据列表（用于向量库）"""
        return [
            {
                "name": p["name"],
                "category": p["category"],
                "price": p["price"],
                "sales": p["sales"],
                "shop_name": p["shop_name"],
                "url": p.get("url", ""),
            }
            for p in self.products_data
        ]

    def get_ids(self) -> List[str]:
        """获取所有商品ID列表"""
        return [str(p["id"]) for p in self.products_data]

    def get_documents(self) -> List[str]:
        """获取所有文档文本（用于向量库）"""
        return [p["search_text"] for p in self.products_data]

    @staticmethod
    def build_search_text(
        name: str,
        category: str,
        description: str,
        shop_name: str,
        max_tokens: int = SEARCH_TEXT_MAX_TOKENS,
    ) -> str:
        """合成检索文本并控制在 token 上限内（默认 512）。"""
        parts = [
            (name or "").strip(),
            (category or "").strip(),
            (description or "").strip(),
            (shop_name or "").strip(),
        ]
        raw = " ".join(part for part in parts if part)
        raw = re.sub(r"\s+", " ", raw).strip()
        if not raw:
            return ""

        tokens = token_counter.encoder.encode(raw)
        if len(tokens) <= max_tokens:
            return raw
        return token_counter.encoder.decode(tokens[:max_tokens])

    def _next_product_id(self) -> int:
        if not self.products_data:
            return 1
        return max(int(p["id"]) for p in self.products_data) + 1

    def add_product(self, product: Dict) -> Dict:
        """追加单条商品到内存与 CSV，并返回完整记录。"""
        product_id = product.get("id") or self._next_product_id()
        name = str(product.get("name", "")).strip()
        category = str(product.get("category", "")).strip() or "未分类"
        description = str(product.get("description", "")).strip()
        shop_name = str(product.get("shop_name", "")).strip() or "未知店铺"
        url = str(product.get("url", "")).strip()

        try:
            price = float(product.get("price", 0) or 0)
        except (TypeError, ValueError):
            price = 0.0

        try:
            sales = int(product.get("sales", 0) or 0)
        except (TypeError, ValueError):
            sales = 0

        search_text = str(product.get("search_text", "")).strip() or self.build_search_text(
            name, category, description, shop_name
        )

        record = {
            "id": int(product_id),
            "name": name,
            "category": category,
            "price": price,
            "description": description,
            "sales": sales,
            "shop_name": shop_name,
            "url": url,
            "search_text": search_text,
        }

        self.products_data.append(record)
        self.corpus.append(search_text)
        self._rewrite_csv()
        return record

    def delete_product(self, product_id: str) -> bool:
        """从内存与 CSV 删除商品；成功返回 True。"""
        target_id = str(product_id)
        before = len(self.products_data)
        self.products_data = [p for p in self.products_data if str(p["id"]) != target_id]
        if len(self.products_data) == before:
            return False

        self.corpus = [p["search_text"] for p in self.products_data]
        self._rewrite_csv()
        return True

    def _rewrite_csv(self) -> None:
        rows = []
        for p in self.products_data:
            row: dict[str, Any] = {}
            for column in CSV_CORE_COLUMNS:
                value = p.get(column, "")
                if value is None:
                    value = ""
                row[column] = value
            rows.append(row)
        df = pd.DataFrame(rows, columns=CSV_CORE_COLUMNS)
        df.to_csv(self.data_path, index=False, encoding="utf-8")
