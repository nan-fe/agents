from app.agents.base_agent import BaseAgent
from app.models.schemas import CopywritingResult, PlanningResult
from app.services.langchain_chains import CopywritingChain
from typing import Optional, Union, Dict
import json


class CopywriterAgent(BaseAgent):
    """文案Agent"""
    
    def __init__(self):
        """初始化文案Agent"""
        super().__init__("Copywriter", "小红书爆款文案写手")
        self.copywriting_chain = CopywritingChain()
    
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
            "history": history,
            "user_input": user_input
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
