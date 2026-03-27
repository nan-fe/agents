from app.agents.base_agent import BaseAgent
from app.models.schemas import CopywritingResult, PlanningResult
from app.services.langchain_chains import CopywritingChain
from typing import Optional
import json


class CopywriterAgent(BaseAgent):
    """文案Agent"""
    
    def __init__(self):
        """初始化文案Agent"""
        super().__init__("Copywriter", "小红书爆款文案写手")
        self.copywriting_chain = CopywritingChain()
    
    async def run(self, planning_result: PlanningResult, log_callback: Optional[callable] = None) -> CopywritingResult:
        """运行文案Agent
        
        Args:
            planning_result: 策划结果
            log_callback: 日志回调函数
            
        Returns:
            文案结果
        """
        await self.log(f"根据策划方案生成文案: {planning_result}", log_callback)
        
        # 构建商品推荐信息
        retrieval_result = ""
        if planning_result.product_recommendations:
            product_info = []
            for product in planning_result.product_recommendations:
                product_info.append(f"{product.product_name}: {product.description}, 链接: {product.taobao_link}, 价格: {product.price or '面议'}")
            retrieval_result = "\n".join(product_info)
            await self.log(f"商品推荐信息: {retrieval_result}", log_callback)
        
        # 构建输入数据
        chain_input = {
            "target_audience": ", ".join(planning_result.target_audience),
            "core_selling_points": ", ".join(planning_result.core_selling_points),
            "tone_style": planning_result.tone_style,
            "retrieval_result": retrieval_result
        }
        
        await self.log("生成小红书风格文案...", log_callback)
  
        # 调用LangChain链
        try:
            result = await self.copywriting_chain.run(chain_input)
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
