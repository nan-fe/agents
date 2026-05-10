"""
答案生成模块 - 基于检索结果或搜索结果生成LLM回答
"""
from langchain_core.prompts import PromptTemplate
from app.config import settings
from app.utils.llm_factory import llm_factory
from typing import List, Dict, Optional


class AnswerGenerator:
    """答案生成器类"""
    
    def __init__(self):
        # 初始化商品推荐提示模板
        self.product_prompt = PromptTemplate(
            template="""你是一个淘宝购物助手。请根据用户问题和检索到的商品信息，给出推荐建议。

用户问题：{query}

商品信息：
{context}

请回答：""",
            input_variables=["query", "context"],
        )
        
        # 初始化搜索结果提示模板
        self.search_prompt = PromptTemplate(
            template="""你是一个淘宝购物助手。请根据用户问题和网络搜索结果，给出推荐建议。

用户问题：{query}

搜索结果：
{context}

请回答：""",
            input_variables=["query", "context"],
        )
    
    async def generate_from_products(self, query: str, products: List[Dict]) -> str:
        """基于检索到的本地商品生成答案"""
        if not products:
            return "抱歉，没有找到相关商品，请尝试其他关键词。"
        
        # 只取第一个商品
        product = products[0]
        context = f"商品名称：{product['name']}\n价格：¥{product['price']}\n销量：{product['sales']}\n店铺：{product['shop_name']}"
        
        try:
            result = await llm_factory.run_chain_with_dynamic_tokens(
                prompt_template=self.product_prompt,
                chain_input={"query": query, "context": context},
                model_name=settings.BASE_MODEL,
                temperature=0.7,
            )
            return result.content
        except Exception as e:
            print(f"generate_from_products 出错: {str(e)}")
            return f"为您找到商品：{product['name']}，价格：¥{product['price']}，店铺：{product['shop_name']}"
    
    async def generate_from_search_results(self, query: str, search_result: str) -> str:
        """基于网络搜索结果生成答案"""
        try:
            result = await llm_factory.run_chain_with_dynamic_tokens(
                prompt_template=self.search_prompt,
                chain_input={"query": query, "context": search_result},
                model_name=settings.BASE_MODEL,
                temperature=0.7,
            )
            return result.content
        except Exception as e:
            print(f"generate_from_search_results 出错: {str(e)}")
            lines = search_result.split("\n")
            product_info = []
            for i, line in enumerate(lines[:2]):
                if line.strip():
                    product_info.append(f"{i+1}. {line.strip()}")
            
            if product_info:
                return f"根据搜索结果，为您找到以下商品信息：\n\n" + "\n".join(product_info)
            else:
                return "抱歉，搜索结果格式无法识别，请尝试其他关键词。"
    
    def fallback_answer(self, query: str, products: Optional[List[Dict]] = None) -> str:
        """降级方案：当其他方案失败时使用"""
        if products and len(products) > 0:
            product = products[0]
            return f"为您找到商品：{product['name']}，价格：¥{product['price']}，店铺：{product['shop_name']}"
        return "抱歉，没有找到相关商品，请尝试其他关键词。"