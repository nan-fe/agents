from app.agents.base_agent import BaseAgent
from typing import Optional, List, Dict, Any
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from app.config import settings


class ProductRagAgent(BaseAgent):
    """商品RAG Agent"""
    
    def __init__(self):
        """初始化商品RAG Agent"""
        super().__init__("RAG", "商品信息检索专家")
        # 构建提示模板
        template = """
        你是一位商品信息检索专家，擅长根据用户输入提取商品信息。
        
        用户输入：{user_input}
        
        请提取相关的商品信息，包括：
        1. 商品名称
        2. 商品描述
        3. 商品价格
        4. 商品特点
        5. 商品链接（如果有）
        
        要求：
        1. 信息要准确、详细
        2. 语言要简洁明了
        3. 输出内容直接是商品信息，不要附加任何解释
        """
        
        prompt = PromptTemplate(
            template=template,
            input_variables=["user_input"]
        )
        
        self.llm = ChatOpenAI(
            model_name=settings.SILICONFLOW_MODEL,
            temperature=0.3,
            api_key=settings.SILICONFLOW_API_KEY,
            base_url=settings.SILICONFLOW_BASE_URL
        )
        
        self.chain = self.prompt | self.llm | StrOutputParser()
    
    async def run(self, input_data: str, log_callback: Optional[callable] = None) -> str:
        """运行商品RAG链
        
        Args:
            input_data: 用户输入
            log_callback: 日志回调函数
            
        Returns:
            商品信息
        """
        try:
            product_info = await self.chain.ainvoke({"user_input": input_data})
            await self.log("商品信息检索完成", log_callback)
            
            return product_info
        except Exception as e:
            # 如果检索失败，返回默认值
            print("rag chain error", e)
            return "默认商品信息"
