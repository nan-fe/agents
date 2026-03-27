from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser
from app.config import settings
from app.models.schemas import CopywritingResult

class CopywritingChain:
    """文案生成链"""
    
    def __init__(self):
        """初始化文案生成链"""
        # 创建 Pydantic 输出解析器
        self.parser = JsonOutputParser(pydantic_object=CopywritingResult)
        
        # 构建提示模板
        template = """
        你是一位小红书爆款文案写手，擅长创作符合小红书风格的文案。
        
        请根据以下信息生成一篇小红书风格的完整文案：
        
        目标人群：{target_audience}
        核心卖点：{core_selling_points}
        语气风格：{tone_style}
        相关商品：{retrieval_result}

        {format_instructions}
        
        要求：
        1. 包含吸引人的标题
        2. 正文内容要生动有趣，使用表情符号
        3. 结尾添加相关话题标签（至少3个）
        4. 整体风格符合小红书平台特点
        5. 如果有相关商品信息，请在文案中自然融入推荐
        6. 输出内容仅包含title、content和hashtags三个字段
        7. 输出内容仅输出 JSON 对象，不要附加任何解释
        """
        
        prompt = PromptTemplate(
            template=template,
            input_variables=["target_audience", "core_selling_points", "tone_style", "retrieval_result"],
            partial_variables={"format_instructions": self.parser.get_format_instructions()}
        )
        
        self.llm = ChatOpenAI(
            model_name=settings.SILICONFLOW_MODEL,
            temperature= 0.3,
            api_key=settings.SILICONFLOW_API_KEY,
            base_url=settings.SILICONFLOW_BASE_URL
        )

        self.chain = prompt | self.llm | self.parser
    
    async def run(self, input_data: dict) -> CopywritingResult:
        """运行文案生成链
        
        Args:
            input_data: 输入数据
            
        Returns:
            生成的文案结果
        """
        return await self.chain.ainvoke(input_data)
