"""
Product RAG Agent
分解成四个阶段：
- 数据加载和存储（包括构建向量库）
- 混合检索+排序
- 质量评估&决策（如果需要网络搜索-则调用DuckDuckGo搜索）
- 答案生成

向量索引与启动解耦：索引在 ensure_index_ready 中完成（可线程池执行），
便于应用先监听端口、再通过 /health/ready 做就绪探针。
"""

import asyncio
from typing import Callable

from app.utils.search_tool import search_duckduckgo_langchain_async

from .answer_generator import AnswerGenerator
from .embeddings import EmbeddingDatabase
from .product_database import ProductDatabase
from .product_scrape_database import ProductScrapeDatabase
from .retrievers.ranker import Ranker
from .retrievers.retriever import HybridRetriever


class ProductRagAgent:
    """产品RAG Agent - 整合所有模块"""

    def __init__(self, data_path: str = None, log_callback: Callable | None = None):
        """
        初始化Agent

        Args:
            data_path: 商品数据CSV路径
            log_callback: 日志回调函数
        """
        # 1. 初始化产品数据库
        self.products_db = ProductDatabase(data_path)
        self.scrape_db = ProductScrapeDatabase(products_csv_path=data_path)

        # 2. 初始化嵌入数据库（向量索引延后到 ensure_index_ready，避免阻塞进程启动）
        self.embedding_db = EmbeddingDatabase()

        self._index_lock: asyncio.Lock | None = None
        self._index_state: str = "pending"  # pending | ready | failed
        self._index_error: str | None = None

        # 3. 初始化检索器和重排器
        self.retriever = HybridRetriever(self.embedding_db, self.products_db)
        self.ranker = Ranker()

        # 4. 初始化答案生成器
        self.answer_generator = AnswerGenerator()

        self.log_callback = log_callback

    def is_rag_index_ready(self) -> bool:
        """供就绪探针：向量索引已成功构建（或库中已有数据并跳过构建）。"""
        return self._index_state == "ready"

    def _build_index_sync(self) -> None:
        """同步构建向量索引（在线程池中执行）。"""
        self.embedding_db.index_documents(
            ids=self.products_db.get_ids(),
            documents=self.products_db.get_documents(),
            metadatas=self.products_db.get_metadata(),
        )

    def add_product_to_index(self, product: dict) -> None:
        """将单条商品写入向量库并刷新 BM25 语料。"""
        product_id = str(product["id"])
        metadata = {
            "name": product["name"],
            "category": product["category"],
            "price": product["price"],
            "sales": product["sales"],
            "shop_name": product["shop_name"],
            "url": product.get("url", ""),
        }
        self.embedding_db.add_documents(
            ids=[product_id],
            documents=[product["search_text"]],
            metadatas=[metadata],
        )
        self.retriever.refresh_corpus()

    def remove_product_from_index(self, product_id: str) -> None:
        """从向量库移除商品并刷新 BM25 语料。"""
        self.embedding_db.delete_documents([str(product_id)])
        self.retriever.refresh_corpus()

    async def ensure_index_ready(self) -> None:
        """确保 Chroma 索引已就绪；并发安全，可重复调用。"""
        if self._index_lock is None:
            self._index_lock = asyncio.Lock()

        if self._index_state == "ready":
            return
        if self._index_state == "failed":
            raise RuntimeError(self._index_error or "RAG 索引构建失败")

        async with self._index_lock:
            if self._index_state == "ready":
                return
            if self._index_state == "failed":
                raise RuntimeError(self._index_error or "RAG 索引构建失败")
            try:
                await asyncio.to_thread(self._build_index_sync)
            except Exception as e:
                self._index_state = "failed"
                self._index_error = str(e)
                raise
            self._index_state = "ready"
            self._index_error = None

    def retrieve_and_rank(self, query: str, top_k: int = 3) -> list:
        """
        执行检索和重排

        Args:
            query: 用户查询
            top_k: 返回的结果数量

        Returns:
            重排后的检索结果列表
        """
        # 混合检索
        results = self.retriever.retrieve(query, top_k)

        # 重排序
        ranked_results = self.ranker.rank(query, results)

        # 返回top_k个结果
        return self.ranker.get_top_k_results(ranked_results, top_k)

    async def run(self, query: str, log_callback: Callable | None = None) -> dict:
        """
        执行RAG流程

        Args:
            query: 用户查询
            log_callback: 日志回调函数

        Returns:
            包含查询、检索结果和答案的字典
        """
        log_cb = log_callback or self.log_callback

        await self.ensure_index_ready()

        print(f"[RagAgent] 开始处理查询: {query}")
        if log_cb:
            await log_cb("RagAgent", f"正在检索商品: {query}")

        # ===== 阶段2：混合检索 + 重排 =====
        products = self.retrieve_and_rank(query, top_k=3)
        print(f"[RagAgent] 检索到 {len(products)} 条商品, 商品列表: {products}")

        # ===== 阶段3：质量评估 & 决策 =====
        product_similarity = 0
        found_relevant = False

        if products:
            # 获取最高分数
            max_score = max(p.get("rank_score", 0) for p in products)
            product_similarity = max_score

            # 阈值判断
            found_relevant = max_score >= 0.4
            print(f"[RagAgent] 最高排序分数: {max_score}, 相关性判断: {found_relevant}")

        # ===== 阶段4：答案生成 =====
        if found_relevant:
            # 路线A：本地商品生成答案
            print("[RagAgent] 使用本地向量库商品生成答案")
            if log_cb:
                await log_cb("RagAgent", f"从本地向量库检索到 {len(products)} 件商品")

            answer = await self.answer_generator.generate_from_products(query, products)

        else:
            # 路线B：网络搜索生成答案
            print(f"[RagAgent] 相关性分数 {product_similarity} 低于阈值，转向网络搜索")
            if log_cb:
                await log_cb("RagAgent", "本地向量库未找到相关商品，使用网络搜索")

            search_result = await search_duckduckgo_langchain_async(query, site="taobao.com")
            print(
                f"[RagAgent] 网络搜索完成，结果长度: {len(search_result) if search_result else 0}"
            )

            if search_result:
                if log_cb:
                    await log_cb("RagAgent", "网络搜索成功获取商品信息")

                answer = await self.answer_generator.generate_from_search_results(
                    query, search_result
                )

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
                if log_cb:
                    await log_cb("RagAgent", "网络搜索也未找到相关商品")

                answer = "抱歉，没有找到相关商品，请尝试其他关键词。"
                products = []

        print("[RagAgent] 生成答案完成", answer)

        return {"query": query, "retrieved_products": products, "answer": answer}
