from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser
from app.config import settings
from app.models.schemas import PlanningResult

class PlanningChain:
    """策划生成链"""
    
    def __init__(self):
        """初始化策划生成链"""
        # 创建 Pydantic 输出解析器
        self.parser = JsonOutputParser(pydantic_object=PlanningResult)
        # 构建提示模板
        template = """
        你是一位小红书资深运营，擅长分析用户需求并转化为创作要点。
        
        请分析以下用户输入，拆解成文案要点和图片需求：
        
        用户输入：{input_data}

        {format_instructions}
        
        要求：
        1. 目标人群要具体，如"学生党"、"职场新人"等
        2. 核心卖点要突出产品或内容的优势
        3. 语气风格要符合小红书平台特点，如"亲切自然"、"活泼可爱"等
        4. 图片需求要详细，包括场景、风格、元素等
        5. 输出内容仅输出 JSON 对象，不要附加任何解释
        """
        
        prompt = PromptTemplate(
            template=template,
            input_variables=["input_data"],
            partial_variables={"format_instructions": self.parser.get_format_instructions()}
        )
        
        self.llm = ChatOpenAI(
            model_name=settings.SILICONFLOW_MODEL,
            temperature=0.7,
            api_key=settings.SILICONFLOW_API_KEY,
            base_url=settings.SILICONFLOW_BASE_URL
        )
        
        self.chain = prompt | self.llm | self.parser
    
    async def run(self, input_data: str) -> PlanningResult:
        """运行策划生成链
        
        Args:
            input_data: 用户输入的描述
            
        Returns:
            策划结果
        """
        return await self.chain.ainvoke({"input_data": input_data})
