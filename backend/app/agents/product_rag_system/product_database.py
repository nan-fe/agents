"""
产品数据库模块 - 管理商品数据的加载、清洗和存储
"""
import os
import pandas as pd
from typing import List, Dict, Optional


class ProductDatabase:
    """商品数据库类"""
    
    def __init__(self, data_path: str = None):
        if data_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            data_path = os.path.join(base_dir, "data", "taobao_products.csv")
        
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
                sample_data = """id,name,category,price,description,sales,shop_name
1,真无线降噪蓝牙耳机,数码,199,蓝牙5.3，主动降噪，30小时续航，IPX7防水,5200,小米官方旗舰店
2,2024夏季纯棉T恤男,男装,49.9,100%纯棉，多色可选，透气亲肤，简约百搭,3400,优衣库官方店
3,苹果iPhone15 Pro,手机,7999,A17 Pro芯片，钛金属边框，4800万像素，灵动岛,1890,Apple官方旗舰店
4,家用全自动咖啡机,家电,899,20bar高压萃取，一键卡布奇诺，可拆卸水箱,2100,德龙电器旗舰店
5,运动跑步鞋女,女鞋,159,网面透气，轻便缓震，防滑耐磨，多色可选,6700,安踏官方店
6,大容量充电宝20000mAh,数码,89,双向快充，数显电量，可上飞机，轻薄便携,9800,罗马仕旗舰店
7,儿童积木玩具益智,母婴,129,大颗粒积木，环保材质，兼容乐高，培养创造力,3100,乐高官方旗舰店
8,不锈钢不粘锅炒锅,厨具,79,无涂层，轻烟不粘，燃气电磁炉通用,4200,苏泊尔官方店
9,男士电动剃须刀,个护,159,浮动三刀头，Type-C充电，全身水洗，续航60分钟,5600,飞科官方旗舰店
10,便携折叠户外桌椅,运动户外,129,铝合金桌面，牛津布椅，承重150kg，收纳方便,1950,探险者户外旗舰店
11,妙界R3至尊版肩颈按摩仪,个护,404,揉捏脖子腰背部颈椎按摩器斜方肌热敷披肩,1950,妙界旗舰店"""
                f.write(sample_data)
            print(f"已自动创建示例数据文件: {self.data_path}")
        else:
            print(f"已加载数据文件: {self.data_path}")
    
    def _load_data(self):
        """加载CSV数据并进行清洗"""
        df = pd.read_csv(self.data_path)
        
        # 去除 ID 列的空格并转换为整数
        df["id"] = df["id"].astype(str).str.strip().astype(int)
        
        # 去除其他列的空格
        for col in ["name", "category", "description", "shop_name"]:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip()
        
        # 合成搜索文本（用于BM25检索）
        df["search_text"] = df.apply(
            lambda row: f"{row['name']} {row['category']} {row['description']} {row['shop_name']}",
            axis=1,
        )
        
        # 保存商品数据和搜索文本
        self.products_data = df.to_dict(orient="records")
        self.corpus = df["search_text"].tolist()
        
        print(f"成功加载 {len(self.products_data)} 条商品数据")
    
    def get_all_products(self) -> List[Dict]:
        """获取所有商品数据"""
        return self.products_data
    
    def get_product_by_id(self, product_id: str) -> Optional[Dict]:
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
                "shop_name": p["shop_name"]
            }
            for p in self.products_data
        ]
    
    def get_ids(self) -> List[str]:
        """获取所有商品ID列表"""
        return [str(p["id"]) for p in self.products_data]
    
    def get_documents(self) -> List[str]:
        """获取所有文档文本（用于向量库）"""
        return [p["search_text"] for p in self.products_data]
