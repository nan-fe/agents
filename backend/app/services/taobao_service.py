from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser
from app.config import settings
from typing import List, Dict, Optional
from app.models.schemas import ProductRecommendation;


class TaobaoService:
    """淘宝商品搜索服务"""
    
    def __init__(self):
        """初始化淘宝商品搜索服务"""
        # 创建 Pydantic 输出解析器
        self.parser = JsonOutputParser(pydantic_object=ProductRecommendation)
        # 构建提示模板
        template = """
        你是一位淘宝商品推荐专家，擅长根据用户需求推荐合适的商品。
        
        请根据以下用户需求，推荐3-5个淘宝商品，并提供商品名称、简短描述、淘宝链接和价格：
        
        用户需求：{user_input}
        
        要求：
        1. 推荐的商品必须与用户需求相关
        2. 每个商品需要包含：
           - product_name: 商品名称
           - description: 商品简短描述（1-2句话）
           - taobao_link: 淘宝链接（格式：https://item.taobao.com/item.htm?id=XXXXXX）
           - price: 商品价格（格式：¥XX.XX）
        3. 输出内容仅输出 JSON 数组，不要附加任何解释
        4. 确保推荐的商品多样化，覆盖不同价位和风格
        """
        
        prompt = PromptTemplate(
            template=template,
            input_variables=["user_input"]
        )
        
        self.llm = ChatOpenAI(
            model_name=settings.SILICONFLOW_MODEL,
            temperature= 1,
            api_key=settings.SILICONFLOW_API_KEY,
            base_url=settings.SILICONFLOW_BASE_URL
        )
        
        self.chain = prompt | self.llm|self.parser
    
    async def search_products(self, user_input: str) -> List[Dict]:
        """搜索淘宝商品
        
        Args:
            user_input: 用户输入的商品需求
            
        Returns:
            商品推荐列表
        """
        try:
            result = await self.chain.ainvoke({"user_input": user_input})
            print("search_products",result)
            return result
        except Exception as e:
            # 如果解析失败，返回默认推荐
            print("search_products",e)
            return self._get_default_recommendations(user_input)
    
    def _get_default_recommendations(self, user_input: str) -> List[Dict]:
        """获取默认商品推荐
        
        Args:
            user_input: 用户输入的商品需求
            
        Returns:
            默认商品推荐列表
        """
        return [
            {
                "product_name": "示例商品1",
                "description": "符合用户需求的优质商品",
                "taobao_link": "https://item.taobao.com/item.htm?id=123456",
                "price": "¥99.99"
            },
            {
                "product_name": "示例商品2",
                "description": "高性价比的选择",
                "taobao_link": "https://item.taobao.com/item.htm?id=654321",
                "price": "¥199.99"
            }
        ]