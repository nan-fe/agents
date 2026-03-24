from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser
from app.config import settings
from app.models.schemas import ReviewResult

class ReviewerChain:
    """审核生成链"""
    
    def __init__(self):
        """初始化审核生成链"""
        # 创建 Pydantic 输出解析器
        self.parser = JsonOutputParser(pydantic_object=ReviewResult)
        # 构建提示模板
        template = """
        你是一位小红书内容审核员，负责检查内容是否违规、合适。
        
        请审核以下内容：
        
        文案标题：{copywriting_title}
        文案内容：{copywriting_content}
        文案标签：{copywriting_hashtags}
        图片URL: {image_url}
        图片提示词：{image_prompt}

        {format_instructions}
        
        审核标准：
        1. 内容是否违反法律法规
        2. 内容是否违反平台规则
        3. 内容是否适合目标人群
        4. 内容是否符合小红书风格
        5. 图片是否清晰、美观
        6. 输出内容仅输出 JSON 对象，不要附加任何解释
        """
        
        prompt = PromptTemplate(
            template=template,
            input_variables=["copywriting_title","copywriting_content","copywriting_hashtags","image_url","image_prompt"],
            partial_variables={"format_instructions": self.parser.get_format_instructions()}
        )
        
        self.llm = ChatOpenAI(
            model_name=settings.SILICONFLOW_MODEL,
            temperature=0.7,
            api_key=settings.SILICONFLOW_API_KEY,
            base_url=settings.SILICONFLOW_BASE_URL
        )
        
        self.chain = prompt | self.llm | self.parser
    
    async def run(self, input_data: dict) -> ReviewResult:
        """运行审核生成链
        
        Args:
            input_data: 用户输入的描述
            
        Returns:
            审核结果
        """
        return await self.chain.ainvoke(input_data)
