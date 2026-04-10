from app.agents.base_agent import BaseAgent
from app.models.schemas import ReviewResult, CopywritingResult, ImageResult
from app.services.reviewer_chain import ReviewerChain
from typing import Optional
import json


class ReviewerAgent(BaseAgent):
    """质检Agent"""
    
    def __init__(self):
        """初始化质检Agent"""
        super().__init__("Reviewer", "小红书内容审核")
        self.reviewer_chain = ReviewerChain()
    
    async def run(self, input_data: dict, log_callback: Optional[callable] = None) -> ReviewResult:
        """运行质检Agent
        
        Args:
            input_data: 包含文案和图片信息的字典
            log_callback: 日志回调函数
            
        Returns:
            审核结果
        """
        # 构建输入数据
        chain_input = {
            "copywriting_title": input_data.get("copywriting_title"),
            "copywriting_content": input_data.get("copywriting_content"),
            "copywriting_hashtags": input_data.get("copywriting_hashtags"),
            "image_url": input_data.get("image_url"),
            "image_prompt": input_data.get("image_prompt")
        }
        
         # 调用审核生成链
        try:
            result = await self.reviewer_chain.run(chain_input)
            await self.log(f"审核完成: {result}", log_callback)
            return ReviewResult(**result)
        except Exception as e:
            print(f"审核失败",e)
            await self.log(f"审核失败: {e}", log_callback)
            # 返回默认值
            return ReviewResult(
                approved=False,
                feedback="审核失败",
                corrections={}
            )
