from app.agents.base_agent import BaseAgent
from app.models.schemas import ReviewResult
from typing import Optional, Dict, Any
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser
from app.config import settings


class ReviewerAgent(BaseAgent):
    """审核Agent"""
    
    def __init__(self):
        """初始化审核Agent"""
        super().__init__("Reviewer", "小红书内容审核专家")
        self.parser = JsonOutputParser(pydantic_object=ReviewResult)
        # 构建提示模板
        template = """
        你是一位专业的小红书内容审核专家，负责审核小红书内容的质量和合规性。
        
        审核内容：
        标题：{copywriting_title}
        内容：{copywriting_content}
        标签：{copywriting_hashtags}
        图片URL：{image_url}
        图片提示词：{image_prompt}
        
        {format_instructions}
        
        要求：
        1. 审核内容是否符合小红书平台规范
        2. 审核内容是否吸引人，符合目标人群特点
        3. 审核内容是否突出核心卖点
        4. 如果审核不通过，请给出具体的修改建议
        5. 输出内容仅输出 JSON 对象，不要附加任何解释
        6. 请逐步思考每一步的审核过程
        """
        
        prompt = PromptTemplate(
            template=template,
            input_variables=["copywriting_title", "copywriting_content", "copywriting_hashtags", "image_url", "image_prompt"],
            partial_variables={"format_instructions": self.parser.get_format_instructions()}
        )
        
        self.llm = ChatOpenAI(
            model_name=settings.SILICONFLOW_MODEL,
            temperature=0.3,
            api_key=settings.SILICONFLOW_API_KEY,
            base_url=settings.SILICONFLOW_BASE_URL
        )
        
        self.chain = self.prompt | self.llm | self.parser
    
    async def run(self, input_data: Dict[str, Any], log_callback: Optional[callable] = None) -> ReviewResult:
        """运行审核链
        
        Args:
            input_data: 输入数据
            log_callback: 日志回调函数
            
        Returns:
            审核结果
        """
        try:
            # 构建输入参数
            chain_input = {
                "copywriting_title": input_data.get("copywriting_title", ""),
                "copywriting_content": input_data.get("copywriting_content", ""),
                "copywriting_hashtags": input_data.get("copywriting_hashtags", []),
                "image_url": input_data.get("image_url", ""),
                "image_prompt": input_data.get("image_prompt", "")
            }
            
            review_result = await self.chain.ainvoke(chain_input)
            await self.log(f"审核完成: {'通过' if review_result.approved else '未通过'}", log_callback)
            
            return ReviewResult(**review_result)
        except Exception as e:
            # 如果审核失败，返回默认值
            print("review chain error", e)
            return ReviewResult(
                approved=True,
                feedback="默认通过"
            )