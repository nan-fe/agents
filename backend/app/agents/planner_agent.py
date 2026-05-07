from app.agents.base_agent import BaseAgent
from app.models.schemas import PlanningResult
from typing import Optional
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser
from app.config import settings
from app.utils.token_counter import token_counter

class PlannerAgent(BaseAgent):
    """策划Agent"""
    
    def __init__(self):
        """初始化策划Agent"""
        super().__init__("Planner", "小红书资深运营")
        self.parser = JsonOutputParser(pydantic_object=PlanningResult)
        # 构建提示模板
        template = """
        你是一位小红书资深运营，擅长分析用户需求并转化为创作要点。
        
        用户输入：{input_data}
        
        历史数据：{history}

        {format_instructions}
        
        要求：
        1. 目标人群要具体，如"学生党"、"职场新人"等
        2. 核心卖点要突出产品或内容的优势
        3. 语气风格要符合小红书平台特点，如"亲切自然"、"活泼可爱"等
        4. 图片需求要详细，包括场景、风格、元素等
        5. 选题内容，25个字以内
        6. 输出内容仅输出 JSON 对象，不要附加任何解释
        7. 输出的内容必须仅包含 target_audience,tone_style,core_selling_points,image_requirements,topic,product_category
        8. 请逐步思考每一步的规划
        9. 如果有历史数据，则按照历史信息，结合用户输入的意见重新调整
        """
        
        self.prompt = PromptTemplate(
            template=template,
            input_variables=["input_data", "history"],
            partial_variables={"format_instructions": self.parser.get_format_instructions()}
        )
        
        self.llm = ChatOpenAI(
            model_name=settings.SILICONFLOW_MODEL,
            temperature=0.3,
            api_key=settings.SILICONFLOW_API_KEY,
            base_url=settings.SILICONFLOW_BASE_URL
        )
        
        self.chain = self.prompt | self.llm | self.parser
    
    def get_llm_with_max_tokens(self, max_tokens: int) -> ChatOpenAI:
        """获取设置了max_tokens的LLM实例
        
        Args:
            max_tokens: 最大输出token数
            
        Returns:
            ChatOpenAI实例
        """
        return ChatOpenAI(
            model_name=settings.SILICONFLOW_MODEL,
            temperature=0.3,
            max_tokens=max_tokens,
            api_key=settings.SILICONFLOW_API_KEY,
            base_url=settings.SILICONFLOW_BASE_URL
        )
    
   
    async def run(self, input_data: str, log_callback: Optional[callable] = None, history: str = "") -> PlanningResult:
        """运行策划生成链
        
        Args:
            input_data: 用户输入的描述
            log_callback: 日志回调函数
            history: 历史数据
            
        Returns:
            策划结果字典
        """
        try:
            # 计算token数
            chain_input = {"input_data": input_data, "history": history or ''}
            # 重新构建prompt以计算token数
            rendered_prompt = self.prompt.format(**chain_input, format_instructions=self.parser.get_format_instructions())
            token_count = token_counter.count_tokens(rendered_prompt, settings.SILICONFLOW_MODEL)
            
            # 分析上下文窗口
            history_tokens = token_counter.count_tokens(history or '', settings.SILICONFLOW_MODEL)
            current_question_tokens = token_counter.count_tokens(input_data, settings.SILICONFLOW_MODEL)
            analysis = token_counter.format_context_analysis(history_tokens, current_question_tokens, settings.SILICONFLOW_MODEL)
            print(f"策划Agent - 输入Token数: {token_count}")
            print(analysis)
            
            # 计算max_tokens
            max_tokens = token_counter.calculate_max_tokens(token_count, settings.SILICONFLOW_MODEL)
            print(f"策划Agent - 最大输出Token数: {max_tokens}")
            
            # 使用动态max_tokens的LLM
            llm_with_max_tokens = self.get_llm_with_max_tokens(max_tokens)
            chain = self.prompt | llm_with_max_tokens | self.parser
            
            planning_result = await chain.ainvoke(chain_input)
            print("plan", planning_result)
            await self.log(f"策划方案生成完成: {planning_result}", log_callback)
            
            return PlanningResult(**planning_result)
        except Exception as e:
            # 如果生成失败，返回默认值
            print("planning chain error", e)
            return PlanningResult(**{
                "target_audience": ["通用人群"],
                "core_selling_points": ["质量好", "价格实惠", "使用方便"],
                "tone_style": "亲切自然",
                "image_requirements": "产品实物图，清晰明亮",
                "topic":"默认主题",
                "product_category":"默认类别"
            })
