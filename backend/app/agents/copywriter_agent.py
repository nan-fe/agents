from app.agents.base_agent import BaseAgent
from app.models.schemas import CopywritingResult, PlanningResult
# from app.services.langchain_chains import CopywritingChain
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser
from app.config import settings
from typing import Optional, Union, Dict


class CopywriterAgent(BaseAgent):
    """文案Agent"""
    
    def __init__(self):
        """初始化文案Agent"""
        super().__init__("Copywriter", "小红书爆款文案写手")
        # self.copywriting_chain = CopywritingChain()
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
    
    async def run(self, planning_result: Union[PlanningResult, Dict], log_callback: Optional[callable] = None, history: str = "") -> CopywritingResult:
        """运行文案Agent
        
        Args:
            planning_result: 策划结果（可以是PlanningResult对象或字典）
            log_callback: 日志回调函数
            history: 历史数据
            
        Returns:
            文案结果
        """
        await self.log(f"根据策划方案生成文案", log_callback)
        
        # 处理不同类型的输入
        if isinstance(planning_result, dict):
            planning_dict = planning_result
            target_audience = planning_dict.get("target_audience", [])
            core_selling_points = planning_dict.get("core_selling_points", [])
            tone_style = planning_dict.get("tone_style", "亲切自然")
            topic = planning_dict.get("topic","默认主题")
            user_input = planning_dict.get("user_input","用户输入")
        else:
            # PlanningResult对象
            planning_dict = planning_result.model_dump()
            target_audience = planning_result.target_audience
            core_selling_points = planning_result.core_selling_points
            tone_style = planning_result.tone_style
            topic = planning_result.topic
            user_input = planning_result.user_input

        
        # 构建输入数据
        chain_input = {
            "target_audience": ", ".join(target_audience) if isinstance(target_audience, list) else target_audience,
            "core_selling_points": ", ".join(core_selling_points) if isinstance(core_selling_points, list) else core_selling_points,
            "tone_style": tone_style,
            "topic": topic,
            "history": history or "",
            "user_input": user_input
        }
        
        await self.log("生成小红书风格文案...", log_callback)
  
        # 调用LangChain链
        try:
            result = await self.chain.ainvoke(chain_input)
            print(f"生成小红书风格文案 result: {result}")
            await self.log(f"文案生成完成: {result}", log_callback)
            # 检查result是否已经是CopywritingResult对象
            if isinstance(result, CopywritingResult):
                return result
            else:
                return CopywritingResult(**result)
        except Exception as e:
            await self.log(f"生成文案失败: {e}", log_callback)
            print(f"生成文案失败: {e}")

            # 返回默认值
            return CopywritingResult(
                title="默认标题",
                content="默认内容",
                hashtags=["#小红书", "#推荐"]
            )
