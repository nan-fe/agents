from app.agents.base_agent import BaseAgent
from app.models.schemas import CopywritingResult
from typing import Optional, Dict, Any
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser
from app.config import settings


class CopywriterAgent(BaseAgent):
    """文案生成Agent"""
    
    def __init__(self):
        """初始化文案生成Agent"""
        super().__init__("Copywriter", "小红书文案专家")
        self.parser = JsonOutputParser(pydantic_object=CopywritingResult)
        # 构建提示模板
        template = """
        你是一位专业的小红书文案专家，擅长根据策划方案和产品信息生成吸引人的小红书文案。
        
        策划方案：
        主题：{topic}
        目标人群：{target_audience}
        核心卖点：{core_selling_points}
        语气风格：{tone_style}
        
        产品信息：
        {product_context}
        
        用户输入：{user_input}
        
        历史数据：{history}
        
        {format_instructions}
        
        要求：
        1. 标题要吸引人，符合小红书风格
        2. 内容要有亲和力，口语化，符合目标人群特点
        3. 要突出核心卖点，自然融入产品信息
        4. 标签要相关，有热门标签和精准标签
        5. 输出内容仅输出 JSON 对象，不要附加任何解释
        6. 请逐步思考每一步的文案创作
        """
        
        prompt = PromptTemplate(
            template=template,
            input_variables=["topic", "target_audience", "core_selling_points", "tone_style", "product_context", "user_input", "history"],
            partial_variables={"format_instructions": self.parser.get_format_instructions()}
        )
        
        self.llm = ChatOpenAI(
            model_name=settings.SILICONFLOW_MODEL,
            temperature=0.7,
            api_key=settings.SILICONFLOW_API_KEY,
            base_url=settings.SILICONFLOW_BASE_URL
        )
        
        self.chain = self.prompt | self.llm | self.parser
    
    async def run(self, input_data: Dict[str, Any], log_callback: Optional[callable] = None, history: str = "") -> CopywritingResult:
        """运行文案生成链
        
        Args:
            input_data: 输入数据
            log_callback: 日志回调函数
            history: 历史数据
            
        Returns:
            文案结果
        """
        try:
            # 构建输入参数
            chain_input = {
                "topic": input_data.get("topic", ""),
                "target_audience": input_data.get("target_audience", []),
                "core_selling_points": input_data.get("core_selling_points", []),
                "tone_style": input_data.get("tone_style", ""),
                "product_context": input_data.get("product_context", ""),
                "user_input": input_data.get("user_input", ""),
                "history": history or ''
            }
            
            copywriting_result = await self.chain.ainvoke(chain_input)
            await self.log(f"文案生成完成: {copywriting_result.title}", log_callback)
            
            return CopywritingResult(**copywriting_result)
        except Exception as e:
            # 如果生成失败，返回默认值
            print("copywriting chain error", e)
            return CopywritingResult(
                title="默认标题",
                content="默认内容",
                hashtags=["#小红书", "#推荐"]
            )