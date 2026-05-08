import os
import pandas as pd
import chromadb
import openai
from dotenv import load_dotenv
from chromadb.api.types import Documents, Embeddings, EmbeddingFunction
from typing import Optional, Callable, List, Dict
from rank_bm25 import BM25Okapi
import numpy as np
from app.config import settings
from app.utils.search_tool import search_duckduckgo_langchain

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
        response = self.client.embeddings.create(model=self.model_name, input=input)
        return [item.embedding for item in response.data]

    @staticmethod
    def name():
        return "siliconflow_free_api"

    def get_model_name(self):
        return self.model_name


class ProductRagAgent:
    def __init__(self, data_path: str = None, log_callback: Optional[Callable] = None):
        if data_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            data_path = os.path.join(base_dir, "data", "taobao_products.csv")
        self.data_path = data_path
        self.model_name = settings.EMBEDING_MODEL
        self.ranker_model = settings.RANKER_MODEL
        self._ensure_data_file()
        self.chroma_client = chromadb.PersistentClient(path="./chroma_taobao_v1")
        self.embedding_fn = SiliconFlowEmbeddingFunction(
            api_key=SILICONFLOW_API_KEY,
            base_url=SILICONFLOW_BASE_URL,
            model_name=self.model_name,
        )

        # 根据模型类型选择距离配置
        # bge-m3 和 bge-large-zh-v1.5 使用余弦距离表现更好
        # bge-large-en-v1.5 使用内积距离表现更好
        if "m3" in self.model_name.lower() or "zh" in self.model_name.lower():
            distance_space = "cosine"  # 余弦距离
        else:
            distance_space = "ip"  # 内积距离

        self.collection = self.chroma_client.get_or_create_collection(
            name="taobao_products",
            embedding_function=self.embedding_fn,
            metadata={"hnsw:space": distance_space},
        )
        self.corpus = []
        self.products_data = []
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
                model=settings.EMBEDING_MODEL, input=texts
            )
            # 返回向量列表
            return [item.embedding for item in response.data]

        return embed_texts

    def _load_or_index_data(self):
        """加载 CSV 数据，如果向量库为空则建立索引"""
        df = pd.read_csv(self.data_path)
        # 去除 ID 列的空格并转换为整数
        df["id"] = df["id"].astype(str).str.strip().astype(int)
        # 去除其他列的空格
        for col in ["name", "category", "description", "shop_name"]:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip()

        df["search_text"] = df.apply(
            lambda row: f"{row['name']} {row['category']} {row['description']} {row['shop_name']}",
            axis=1,
        )

        # 保存商品数据用于关键词检索
        self.products_data = df.to_dict(orient="records")
        self.corpus = df["search_text"].tolist()

        if self.collection.count() > 0:
            print(f"已有 {self.collection.count()} 条商品向量，跳过索引")
            return

        ids = df["id"].astype(str).tolist()
        documents = df["search_text"].tolist()
        metadatas = df[["name", "category", "price", "sales", "shop_name"]].to_dict(
            orient="records"
        )

        batch_size = 100
        for i in range(0, len(ids), batch_size):
            self.collection.add(
                ids=ids[i : i + batch_size],
                documents=documents[i : i + batch_size],
                metadatas=metadatas[i : i + batch_size],
            )
        print(f"成功索引 {len(ids)} 条淘宝商品")

    def bm25_retrieve(self, query: str, top_k: int = 1):
        """使用关键词匹配进行检索"""
        if not self.corpus:
            return []

        # 改进的关键词匹配分数计算
        scores = []
        query_words = query.split()

        for doc in self.corpus:
            # 计算每个查询词在文档中的出现次数
            score = 0
            for word in query_words:
                # 检查词是否在文档中出现
                if word in doc:
                    score += 1
                # 对于中文，也检查每个字符是否在文档中出现
                for char in word:
                    if char in doc:
                        score += 0.1
            scores.append(score)

        # 获取 top_k 个最高分的索引
        top_indices = np.argsort(scores)[::-1][:top_k]

        retrieved = []
        for idx in top_indices:
            product = self.products_data[idx]
            retrieved.append(
                {
                    "id": str(product["id"]),
                    "name": product["name"],
                    "category": product["category"],
                    "price": product["price"],
                    "sales": product["sales"],
                    "shop_name": product["shop_name"],
                    "bm25_score": float(scores[idx]),
                }
            )
        return retrieved

    def rank_results(self, query: str, results: List[Dict]) -> List[Dict]:
        """使用混合分数对检索结果进行重排序"""
        if not results:
            return []

        # 直接使用混合分数排序，避免调用不存在的模型
        for item in results:
            # 计算混合分数
            semantic_score = item.get("similarity", 0)
            bm25_score = item.get("bm25_score", 0)
            # 归一化 BM25 分数 - 使用固定的归一化因子
            # 基于经验，BM25 分数通常不会超过 5，所以使用 5 作为归一化因子
            if bm25_score > 0:
                bm25_score = min(1.0, bm25_score / 5.0)
            # 加权平均计算最终分数
            item["rank_score"] = semantic_score * 0.6 + bm25_score * 0.4

        # 按排序分数排序
        results.sort(key=lambda x: x.get("rank_score", 0), reverse=True)
        return results

    def retrieve(self, query: str, top_k: int = 3):
        """检索最相似的商品，结合向量检索和 BM25 检索"""
        # 向量检索
        vector_results = self.collection.query(
            query_texts=[query], n_results=top_k, include=["metadatas", "distances"]
        )

        vector_retrieved = []
        for i in range(len(vector_results["ids"][0])):
            meta = vector_results["metadatas"][0][i]
            distance = vector_results["distances"][0][i]

            # 根据模型类型计算相似度
            if "m3" in self.model_name.lower() or "zh" in self.model_name.lower():
                similarity = 1 - distance
            else:
                similarity = max(0, 1 - distance)

            vector_retrieved.append(
                {
                    "id": vector_results["ids"][0][i],
                    "name": meta["name"],
                    "category": meta["category"],
                    "price": meta["price"],
                    "sales": meta["sales"],
                    "shop_name": meta["shop_name"],
                    "similarity": similarity,
                    "bm25_score": 0.0,  # 初始化 BM25 分数
                }
            )

        # 关键词检索
        bm25_retrieved = self.bm25_retrieve(query, top_k)

        # 合并结果，去重
        merged_results = {}

        # 添加向量检索结果
        for item in vector_retrieved:
            merged_results[item["id"]] = item

        # 添加 BM25 检索结果
        for item in bm25_retrieved:
            if item["id"] in merged_results:
                # 如果已经存在，合并分数
                merged_results[item["id"]]["bm25_score"] = item["bm25_score"]
            else:
                # 确保新添加的商品也有相似度字段
                item["similarity"] = 0.0
                merged_results[item["id"]] = item

        # 转换为列表
        final_results = list(merged_results.values())

        # 使用 RANKER_MODEL 重排序
        final_results = self.rank_results(query, final_results)

        # 截取 top_k 个结果
        return final_results[:top_k]

    def generate_answer(self, query: str, retrieved_products):
        """使用硅基流动的 Qwen 对话模型生成回答"""
        if not retrieved_products:
            return "抱歉，没有找到相关商品，请尝试其他关键词。"

        context = "\n".join(
            [
                f"{i+1}. {p['name']} | ¥{p['price']} | 销量 {p['sales']} | 店铺：{p['shop_name']}"
                for i, p in enumerate(retrieved_products)
            ]
        )

        try:
            system_prompt = """你是一个淘宝购物助手。请根据用户问题和检索到的商品列表，给出推荐建议。
                - 如果用户有明确的预算、功能偏好，请优先推荐最匹配的商品。
                - 回答要简洁、友好，并包含商品名称、价格和推荐理由。
                - 如果信息不足，可以询问用户更多细节。"""

            user_prompt = f"用户问题：{query}\n\n相关商品：\n{context}\n\n请回答："

            # 使用之前初始化的 client，添加超时设置
            response = client.chat.completions.create(
                model=settings.GENARATION_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                max_tokens=300,
                timeout=10,  # 添加超时设置
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"generate_answer 出错: {str(e)}")
            # 出错时使用简单回答
            product = retrieved_products[0]
            return f"为您找到商品：{product['name']}，价格：¥{product['price']}，店铺：{product['shop_name']}"

    async def run(self, query: str, log_callback: Optional[Callable] = None):
        print("query", query)
        if log_callback:
            await log_callback("RagAgent", f"正在检索商品: {query}")

        # 从本地向量库检索商品
        products = self.retrieve(query, 3)
        product_similarity = 0
        print("从本地向量库检索商品")
        # 检查是否找到相关商品（考虑重排序后的分数）
        found_relevant = False
        if products:
            # 遍历所有检索到的商品，取最高的 rank_score 或 similarity 值
            if "rank_score" in products[0]:
                max_score = max(product.get("rank_score", 0) for product in products)
                found_relevant = max_score >= 0.4  # 调整阈值，确保相关性
                product_similarity = max_score
                print(f"最高排序分数: {max_score}")
            else:
                # 回退到使用 similarity
                max_similarity = max(
                    product.get("similarity", 0) for product in products
                )
                found_relevant = max_similarity >= 0.3  # 调整阈值，确保相关性
                product_similarity = max_similarity
                print(f"最高相似度: {max_similarity}")
        print(f"found_relevant: {found_relevant}")

        if found_relevant:
            print("使用本地向量库商品")
            # 找到相关商品，使用本地数据生成回答
            if log_callback:
                await log_callback(
                    "RagAgent", f"从本地向量库检索到 {len(products)} 件商品"
                )

            try:
                answer = self.generate_answer(query, products)
            except Exception as e:
                print(f"生成回答出错: {str(e)}")
                # 出错时使用简单回答
                product = products[0]
                answer = f"为您找到商品：{product['name']}，价格：¥{product['price']}，店铺：{product['shop_name']}"
        else:
            # 没有找到相关商品，使用网络搜索
            print("没有找到相关商品，使用网络搜索", product_similarity)
            if log_callback:
                await log_callback("RagAgent", "本地向量库未找到相关商品，使用网络搜索")

            # # 使用网络搜索获取商品信息
            search_result = search_duckduckgo_langchain(query, site="taobao.com")
            print("使用网络搜索获取商品信息", search_result)

            if search_result:
                # 基于搜索结果生成回答
                if log_callback:
                    await log_callback("RagAgent", "网络搜索成功获取商品信息")

                try:
                    # 使用 LLM 基于搜索结果生成回答
                    system_prompt = """你是一个淘宝购物助手。请根据用户问题和网络搜索结果，给出推荐建议。
                    - 回答要简洁、友好，包含商品名称、价格和推荐理由。
                    - 如果信息不足，可以询问用户更多细节。"""

                    user_prompt = f"用户问题：{query}\n\n网络搜索结果：\n{search_result}\n\n请回答："
                    print("user_prompt", user_prompt)

                    response = client.chat.completions.create(
                        model=settings.GENARATION_MODEL,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        temperature=0.7,
                        max_tokens=300,
                        timeout=10,  # 添加超时设置
                    )
                    print("response end")
                    answer = response.choices[0].message.content
                    print("ans", answer)
                except Exception as e:
                    print(f"LLM 调用出错: {str(e)}")
                    # 超时或出错时，直接使用搜索结果生成简单回答
                    lines = search_result.split("\n")
                    product_info = []
                    for i, line in enumerate(lines[:2]):  # 取前2行
                        if line.strip():
                            product_info.append(f"{i+1}. {line.strip()}")

                    if product_info:
                        answer = (
                            f"根据搜索结果，为您找到以下商品信息：\n\n"
                            + "\n".join(product_info)
                        )
                    else:
                        answer = "抱歉，搜索结果格式无法识别，请尝试其他关键词。"

                # 构建搜索结果格式
                products = [
                    {
                        "id": "search",
                        "name": "网络搜索结果",
                        "description": search_result[:200] + "...",
                    }
                ]
            else:
                # 网络搜索也失败
                if log_callback:
                    await log_callback("RagAgent", "网络搜索也未找到相关商品")
                answer = "抱歉，没有找到相关商品，请尝试其他关键词。"
                products = []

        print("结束", products)
        return {"query": query, "retrieved_products": products, "answer": answer}
        # return {'query': '推荐一款适合学生党的平价防晒霜', 'retrieved_products': [{'id': '2', 'name': '2024夏季纯棉T恤男', 'category': '男装', 'price': 49.9, 'sales': 3400, 'shop_name': '优衣库官方店', 'similarity': -0.3087165355682373}], 'answer': '抱歉，您要找的防晒霜相关商品暂未匹配到。目前提供的商品是男士纯棉T恤，可能不是您需要的。建议您重新搜索“学生党平价防晒霜”或提供更多需求，如防晒指数、质地（清爽/滋润）、是否适合敏感肌等，我可以为您更精准推荐！'}
