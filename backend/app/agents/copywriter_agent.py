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
    
    async def run(self, input_data: dict, log_callback: Optional[callable] = None) -> CopywritingResult:
        """运行文案Agent
        
        Args:
            input_data: 包含策划结果和检索结果的字典
            log_callback: 日志回调函数
            
        Returns:
            文案结果
        """
        # 提取策划结果和检索结果
        planning_result = input_data.get("planning_result")
        retrieval_result = input_data.get("retrieval_result")
        
        await self.log(f"根据策划方案生成文案: {planning_result}", log_callback)
        if retrieval_result:
            await self.log(f"检索结果: {retrieval_result}", log_callback)
        
        # 构建输入数据
        chain_input = {
            "target_audience": planning_result.target_audience,
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
