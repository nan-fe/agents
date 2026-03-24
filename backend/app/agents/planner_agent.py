from app.agents.base_agent import BaseAgent
from app.models.schemas import PlanningResult
from app.services.planning_chain import PlanningChain
from typing import Optional


class PlannerAgent(BaseAgent):
    """策划Agent"""
    
    def __init__(self):
        """初始化策划Agent"""
        super().__init__("Planner", "小红书资深运营")
        self.planning_chain = PlanningChain()
    
    async def run(self, input_data: str, log_callback: Optional[callable] = None) -> PlanningResult:
        """运行策划Agent
        
        Args:
            input_data: 用户输入的描述
            log_callback: 日志回调函数
            
        Returns:
            策划结果
        """
        await self.log(f"分析用户输入: {input_data}", log_callback)
        
        await self.log("生成策划方案...", log_callback)
        
        # 调用策划生成链
        try:
            result = await self.planning_chain.run(input_data)
            await self.log(f"策划方案生成完成: {result}", log_callback)
            return PlanningResult(**result)
        except Exception as e:
            await self.log(f"生成策划方案失败: {e}", log_callback)
            # 返回默认值
            return PlanningResult(
                target_audience="通用人群",
                core_selling_points=["质量好", "价格实惠", "使用方便"],
                tone_style="亲切自然",
                image_requirements="产品实物图，清晰明亮"
            )
