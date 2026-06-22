"""
检索模块 - 实现向量检索、BM25检索和混合检索
"""

from typing import Dict, List

import numpy as np


class Retriever:
    """检索器基类"""

    def retrieve(self, query: str, top_k: int) -> List[Dict]:
        raise NotImplementedError


class VectorRetriever(Retriever):
    """向量相似度检索器"""

    def __init__(self, embedding_db, products_db):
        self.embedding_db = embedding_db
        self.products_db = products_db

    def retrieve(self, query: str, top_k: int = 3) -> List[Dict]:
        """执行向量检索"""
        results = self.embedding_db.query(query, top_k)

        retrieved = []
        for i in range(len(results["ids"][0])):
            meta = results["metadatas"][0][i]
            distance = results["distances"][0][i]

            # 将距离转换为相似度
            similarity = self.embedding_db.similarity_to_score(distance)

            retrieved.append(
                {
                    "id": results["ids"][0][i],
                    "name": meta["name"],
                    "category": meta["category"],
                    "price": meta["price"],
                    "sales": meta["sales"],
                    "shop_name": meta["shop_name"],
                    "url": meta.get("url", ""),
                    "similarity": similarity,
                    "bm25_score": 0.0,
                }
            )

        return retrieved


class BM25Retriever(Retriever):
    """BM25关键词检索器"""

    def __init__(self, products_db):
        self.products_db = products_db
        self.refresh_corpus()

    def refresh_corpus(self) -> None:
        """商品库变更后刷新 BM25 语料。"""
        self.corpus = self.products_db.get_corpus()
        self.products_data = self.products_db.get_all_products()

    def retrieve(self, query: str, top_k: int = 3) -> List[Dict]:
        """执行BM25检索"""
        if not self.corpus:
            return []

        # 简单的关键词匹配分数计算
        scores = []
        query_words = query.split()

        for doc in self.corpus:
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
                    "url": product.get("url", ""),
                    "similarity": 0.0,
                    "bm25_score": float(scores[idx]),
                }
            )

        return retrieved


class HybridRetriever(Retriever):
    """混合检索器 - 融合向量检索和BM25检索"""

    def __init__(self, embedding_db, products_db):
        self.vector_retriever = VectorRetriever(embedding_db, products_db)
        self.bm25_retriever = BM25Retriever(products_db)

    def refresh_corpus(self) -> None:
        """商品库变更后刷新 BM25 语料。"""
        self.bm25_retriever.refresh_corpus()

    def retrieve(self, query: str, top_k: int = 3) -> List[Dict]:
        """执行混合检索"""
        # 向量检索
        vector_results = self.vector_retriever.retrieve(query, top_k)

        # BM25检索
        bm25_results = self.bm25_retriever.retrieve(query, top_k)

        # 合并结果，去重
        merged_results = {}

        # 添加向量检索结果
        for item in vector_results:
            merged_results[item["id"]] = item

        # 添加BM25检索结果
        for item in bm25_results:
            if item["id"] in merged_results:
                # 已存在则合并分数
                merged_results[item["id"]]["bm25_score"] = item["bm25_score"]
            else:
                # 新项目补充相似度字段
                item["similarity"] = 0.0
                merged_results[item["id"]] = item

        # 转换为列表
        final_results = list(merged_results.values())

        return final_results
