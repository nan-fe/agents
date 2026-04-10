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
        文案主题：{topic}
        历史数据：{history}
        用户输入：{user_input}

        {format_instructions}
        
        重要要求：
        1. 必须输出一个JSON对象，包含以下三个字段：
           - title: 文案标题（字符串）
           - content: 文案正文（字符串）
           - hashtags: 话题标签（字符串数组）
        
        2. 如果有历史数据，则按照历史信息，结合用户输入的意见重新调整对应的点
        3. 标题要吸引人，能引起用户兴趣
        3. 正文内容要生动有趣，使用表情符号，至少100字
        4. 话题标签至少3个，格式如：["#标签1", "#标签2", "#标签3"]
        5. 整体风格符合小红书平台特点
        6. 如果有相关商品信息，请在文案中自然融入推荐
    
        
        严格按照这个格式输出示例：
        {{
            "title": "🔥必买好物推荐！这个神器让你爱不释手！",
            "content": "亲们，今天给大家安利一个超棒的产品！✨\n\n...",
            "hashtags": ["#好物推荐", "#必买清单", "#小红书种草"]
        }}
        
        注意：仅输出JSON对象，不要附加任何解释或额外文字。
        """
        
        prompt = PromptTemplate(
            template=template,
            input_variables=["target_audience", "core_selling_points", "tone_style", "topic", "history","user_input"],
            partial_variables={"format_instructions": self.parser.get_format_instructions()}
        )
        
        self.llm = ChatOpenAI(
            model_name=settings.COPYWRITE_MODEL,
            temperature=0.7,
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
        # 确保information_summary字段存在
        if "information_summary" not in input_data:
            input_data["information_summary"] = ""
        
        # 确保history字段存在
        if "history" not in input_data:
            input_data["history"] = ""
        
        return await self.chain.ainvoke(input_data)
