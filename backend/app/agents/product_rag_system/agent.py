"""
Product RAG Agent
分解成四个阶段：
- 数据加载和存储（包括构建向量库）
- 混合检索+排序
- 质量评估&决策（如果需要网络搜索-则调用DuckDuckGo搜索）
- 答案生成
"""
from typing import Optional, Callable

from .product_database import ProductDatabase
from .embeddings import EmbeddingDatabase
from .retrievers.retriever import HybridRetriever
from .retrievers.ranker import Ranker
from .answer_generator import AnswerGenerator
from app.utils.search_tool import search_duckduckgo_langchain

class ProductRagAgent:
    """产品RAG Agent - 整合所有模块"""
    
    def __init__(self, data_path: str = None, log_callback: Optional[Callable] = None):
        """
        初始化Agent
        
        Args:
            data_path: 商品数据CSV路径
            log_callback: 日志回调函数
        """
        # 1. 初始化产品数据库
        self.products_db = ProductDatabase(data_path)
        
        # 2. 初始化嵌入数据库
        self.embedding_db = EmbeddingDatabase()
        
        # 索引商品数据
        self.embedding_db.index_documents(
            ids=self.products_db.get_ids(),
            documents=self.products_db.get_documents(),
            metadatas=self.products_db.get_metadata()
        )
        
        # 3. 初始化检索器和重排器
        self.retriever = HybridRetriever(self.embedding_db, self.products_db)
        self.ranker = Ranker()
        
        # 4. 初始化答案生成器
        self.answer_generator = AnswerGenerator()
        
        self.log_callback = log_callback
    
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
    
    async def run(self, query: str, log_callback: Optional[Callable] = None) -> dict:
        """
        执行RAG流程
        
        Args:
            query: 用户查询
            log_callback: 日志回调函数
        
        Returns:
            包含查询、检索结果和答案的字典
        """
        log_cb = log_callback or self.log_callback
        
        print(f"[RagAgent] 开始处理查询: {query}")
        if log_cb:
            await log_cb("RagAgent", f"正在检索商品: {query}")
        
        # ===== 阶段2：混合检索 + 重排 =====
        products = self.retrieve_and_rank(query, top_k=3)
        print(f"[RagAgent] 检索到 {len(products)} 条商品")
        
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
            
            search_result = search_duckduckgo_langchain(query, site="taobao.com")
            print(f"[RagAgent] 网络搜索完成，结果长度: {len(search_result) if search_result else 0}")
            
            if search_result:
                if log_cb:
                    await log_cb("RagAgent", "网络搜索成功获取商品信息")
                
                answer = await self.answer_generator.generate_from_search_results(query, search_result)
                
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
        
        print(f"[RagAgent] 生成答案完成", answer)
        
        return {
            "query": query,
            "retrieved_products": products,
            "answer": answer
        }
