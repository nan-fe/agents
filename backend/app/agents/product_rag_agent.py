import os
import pandas as pd
import chromadb
import openai
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from chromadb.api.types import Documents, Embeddings, EmbeddingFunction
from typing import Optional, Callable
from app.config import settings

load_dotenv()

SILICONFLOW_API_KEY = os.getenv("SILICONFLOW_API_KEY")
SILICONFLOW_BASE_URL = "https://api.siliconflow.cn/v1"

# 初始化 OpenAI 客户端
client = openai.OpenAI(
    api_key=SILICONFLOW_API_KEY,
    base_url=SILICONFLOW_BASE_URL,
)


class SiliconFlowEmbeddingFunction(EmbeddingFunction[Documents]):
    def __init__(self, api_key, base_url, model_name=settings.EMBEDING_MODEL):
        self.api_key = api_key
        self.base_url = base_url
        self.model_name = model_name
        self.client = openai.OpenAI(api_key=api_key, base_url=base_url)

    def __call__(self, input: Documents) -> Embeddings:
        # 直接使用 'input' 作为参数名
        response = self.client.embeddings.create(
            model=self.model_name,
            input=input
        )
        return [item.embedding for item in response.data]

    @staticmethod
    def name():
        return "siliconflow_free_api"

class ProductRagAgent:
    def __init__(self, data_path: str = None,log_callback: Optional[Callable] = None):
        if data_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            data_path = os.path.join(base_dir, "data", "taobao_products.csv")
        self.data_path = data_path
        self._ensure_data_file()
        self.chroma_client = chromadb.PersistentClient(path="./chroma_taobao_v1")
        self.embedding_fn = SiliconFlowEmbeddingFunction(
            api_key=SILICONFLOW_API_KEY,
            base_url=SILICONFLOW_BASE_URL,
            model_name=settings.EMBEDING_MODEL
        )
        self.collection = self.chroma_client.get_or_create_collection(
            name="taobao_products",
            embedding_function=self.embedding_fn
        )
        self._load_or_index_data()
        
    def _ensure_data_file(self):
        if not os.path.exists(self.data_path):
            os.makedirs(os.path.dirname(self.data_path), exist_ok=True)
            with open(self.data_path, "w", encoding="utf-8") as f:
                # 生成示例 CSV（使用之前提供的 10 条商品数据）
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
                    11,妙界R3至尊版肩颈按摩仪,个护,404,揉捏脖子腰背部颈椎按摩器斜方肌热敷披肩,1950,妙界旗舰店
                    """
                f.write(sample_data)
            print(f"已自动创建示例数据文件: {self.data_path}")
        else:
            print(f"已创建数据文件: {self.data_path}")

    def _create_embedding_function(self):
        """创建一个符合 Chroma 要求的 embedding function"""
        def embed_texts(texts):
            # 硅基流动的嵌入 API 调用
            response = client.embeddings.create(
                model=settings.EMBEDING_MODEL,
                input=texts
            )
            # 返回向量列表
            return [item.embedding for item in response.data]
        return embed_texts

    def _load_or_index_data(self):
        """加载 CSV 数据，如果向量库为空则建立索引"""
        if self.collection.count() > 0:
            print(f"已有 {self.collection.count()} 条商品向量，跳过索引")
            return

        df = pd.read_csv(self.data_path)
        df["search_text"] = df.apply(
            lambda row: f"{row['name']} {row['category']} {row['description']} {row['shop_name']}",
            axis=1
        )

        ids = df["id"].astype(str).tolist()
        documents = df["search_text"].tolist()
        metadatas = df[["name", "category", "price", "sales", "shop_name"]].to_dict(orient="records")

        batch_size = 100
        for i in range(0, len(ids), batch_size):
            self.collection.add(
                ids=ids[i:i+batch_size],
                documents=documents[i:i+batch_size],
                metadatas=metadatas[i:i+batch_size]
            )
        print(f"成功索引 {len(ids)} 条淘宝商品")

    def retrieve(self, query: str, top_k: int = 1):
        """检索最相似的商品"""
        results = self.collection.query(
            query_texts=[query],
            n_results=top_k,
            include=["metadatas", "distances"]
        )
        retrieved = []
        for i in range(len(results["ids"][0])):
            meta = results["metadatas"][0][i]
            retrieved.append({
                "id": results["ids"][0][i],
                "name": meta["name"],
                "category": meta["category"],
                "price": meta["price"],
                "sales": meta["sales"],
                "shop_name": meta["shop_name"],
                "similarity": 1 - results["distances"][0][i]
            })
        return retrieved

    def generate_answer(self, query: str, retrieved_products):
        """使用硅基流动的 Qwen 对话模型生成回答"""
        if not retrieved_products:
            return "抱歉，没有找到相关商品，请尝试其他关键词。"

        context = "\n".join([
            f"{i+1}. {p['name']} | ¥{p['price']} | 销量 {p['sales']} | 店铺：{p['shop_name']}"
            for i, p in enumerate(retrieved_products)
        ])

        system_prompt = """你是一个淘宝购物助手。请根据用户问题和检索到的商品列表，给出推荐建议。
            - 如果用户有明确的预算、功能偏好，请优先推荐最匹配的商品。
            - 回答要简洁、友好，并包含商品名称、价格和推荐理由。
            - 如果信息不足，可以询问用户更多细节。"""

        user_prompt = f"用户问题：{query}\n\n相关商品：\n{context}\n\n请回答："

        # 使用之前初始化的 client
        response = client.chat.completions.create(
            model=settings.GENARATION_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=300
        )
        return response.choices[0].message.content

    async def run(self, query: str,log_callback: Optional[Callable] = None):
        print("query",query)
        if log_callback:
            await log_callback("RagAgent", f"正在检索商品: {query}")
        products = self.retrieve(query, 1)
        answer = self.generate_answer(query, products)
        if log_callback:
            await log_callback("RagAgent", f"检索到 {len(products)} 件商品")
        return {
            "query": query,
            "retrieved_products": products,
            "answer": answer
        }
        # return {'query': '推荐一款适合学生党的平价防晒霜', 'retrieved_products': [{'id': '2', 'name': '2024夏季纯棉T恤男', 'category': '男装', 'price': 49.9, 'sales': 3400, 'shop_name': '优衣库官方店', 'similarity': -0.3087165355682373}], 'answer': '抱歉，您要找的防晒霜相关商品暂未匹配到。目前提供的商品是男士纯棉T恤，可能不是您需要的。建议您重新搜索“学生党平价防晒霜”或提供更多需求，如防晒指数、质地（清爽/滋润）、是否适合敏感肌等，我可以为您更精准推荐！'}