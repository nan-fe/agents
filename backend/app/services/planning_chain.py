from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser
from app.config import settings
from app.models.schemas import PlanningResult
from app.services.taobao_service import TaobaoService

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
        5. 识别用户输入的商品类型
        6. 输出内容仅输出 JSON 对象，不要附加任何解释
        7. 输出的内容必须仅包含target_audience,tone_style,core_selling_points,image_requirements,product_category字段
        """
        
        prompt = PromptTemplate(
            template=template,
            input_variables=["input_data"],
            partial_variables={"format_instructions": self.parser.get_format_instructions()}
        )
        
        self.llm = ChatOpenAI(
            model_name=settings.SILICONFLOW_MODEL,
            temperature=0.3,
            api_key=settings.SILICONFLOW_API_KEY,
            base_url=settings.SILICONFLOW_BASE_URL
        )
        
        self.chain = prompt | self.llm | self.parser
        self.taobao_service = TaobaoService()
    
    async def run(self, input_data: str) -> dict:
        """运行策划生成链
        
        Args:
            input_data: 用户输入的描述
            
        Returns:
            策划结果字典
        """
        try:
            # 获取商品推荐
            product_recommendations = await self.taobao_service.search_products(input_data)
            print("product_recommendations", product_recommendations)
            
            # 生成策划方案
            if product_recommendations:
                key_input = product_recommendations[0]["product_name"]
                print("key_input", key_input)
            else:
                key_input = input_data
              
            planning_result = await self.chain.ainvoke({"input_data": key_input})
            print("plan", planning_result)
            
            # 添加商品推荐到策划结果
            planning_result_dict = planning_result
            if isinstance(planning_result, dict):
                print("dict")
                # 确保包含所有必填字段
                if "image_requirements" not in planning_result_dict:
                    planning_result_dict["image_requirements"] = "产品实物图，清晰明亮"
                planning_result_dict["product_recommendations"] = product_recommendations
            else:
                print("no-dict")
                planning_result_dict = planning_result.model_dump()
                planning_result_dict["product_recommendations"] = product_recommendations
            
            print("planning_result_dict", planning_result_dict)
            return planning_result_dict
        except Exception as e:
            # 如果生成失败，返回默认值
            print("planning chain error", e)
            return {
                "target_audience": ["通用人群"],
                "core_selling_points": ["质量好", "价格实惠", "使用方便"],
                "tone_style": "亲切自然",
                "image_requirements": "产品实物图，清晰明亮",
                "product_recommendations": [],
                "product_category":"通用产品"
            }
