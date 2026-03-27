from app.agents.planner_agent import PlannerAgent
from app.agents.copywriter_agent import CopywriterAgent
from app.agents.image_agent import ImageAgent
from app.agents.reviewer_agent import ReviewerAgent
from typing import Optional, Callable
import asyncio


class AgentOrchestrator:
    """Agent协调器"""
    
    def __init__(self):
        """初始化协调器"""
        self.planner_agent = PlannerAgent()
        self.copywriter_agent = CopywriterAgent()
        self.image_agent = ImageAgent()
        self.reviewer_agent = ReviewerAgent()
    
    async def run(self, user_input: str, log_callback: Optional[Callable] = None) -> dict:
        """运行多Agent协作流程
        
        Args:
            user_input: 用户输入
            log_callback: 日志回调函数
            
        Returns:
            最终结果
        """
        # 1. 策划Agent分析用户输入
        planning_result = await self.planner_agent.run(user_input, log_callback)
        
        # 2. 并行执行文案Agent和图片Agent
        copywriting_task = self.copywriter_agent.run(planning_result, log_callback)
        image_task = self.image_agent.run(planning_result, log_callback)
        
        copywriting_result, image_result = await asyncio.gather(
            copywriting_task,
            image_task
        )
        
        # 3. 质检Agent审核
        review_input = {
            "copywriting_title": copywriting_result.title,
            "copywriting_content": copywriting_result.content,
            "copywriting_hashtags": copywriting_result.hashtags,
            "image_url": image_result.image_url,
            "image_prompt": image_result.prompt
        }
        
        review_result = await self.reviewer_agent.run(review_input, log_callback)
        
        # 4. 处理审核结果（最多重试2次）
        retry_count = 0
        max_retries = 2
        
        while not review_result.approved and retry_count < max_retries:
            retry_count += 1
            await log_callback("Orchestrator", f"审核未通过，第{retry_count}次修改")
            
            # 根据审核反馈修改
            if review_result.corrections:
                # 这里简化处理，实际项目中应该根据具体的修改建议进行调整
                await log_callback("Orchestrator", f"根据审核反馈修改内容: {review_result.corrections}")
            
            # 重新生成文案和图片
            copywriting_result = await self.copywriter_agent.run(planning_result, log_callback)
            image_result = await self.image_agent.run(planning_result, log_callback)
            
            # 重新审核
            review_input = {
                "copywriting_title": copywriting_result.title,
                "copywriting_content": copywriting_result.content,
                "copywriting_hashtags": copywriting_result.hashtags,
                "image_url": image_result.image_url,
                "image_prompt": image_result.prompt
            }
        
            review_result = await self.reviewer_agent.run(review_input, log_callback)
        
        # 5. 整合最终结果
        final_result = {
            "title": copywriting_result.title,
            "content": copywriting_result.content,
            "hashtags": copywriting_result.hashtags,
            "image_url": image_result.image_url
        }
        
        # 添加商品推荐信息
        if hasattr(planning_result, "product_recommendations") and planning_result.product_recommendations:
            product_recommendations = []
            for product in planning_result.product_recommendations:
                product_recommendations.append({
                    "product_name": product.product_name,
                    "description": product.description,
                    "taobao_link": product.taobao_link,
                    "price": product.price
                })
            final_result["product_recommendations"] = product_recommendations
        
        await log_callback("Orchestrator", f"多Agent协作完成，生成最终结果: {final_result}")
        
        return final_result
