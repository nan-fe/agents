from app.config import settings
from openai import AsyncOpenAI


class SiliconFlowService:
    """SiliconFlow服务封装"""
    
    def __init__(self):
        """初始化SiliconFlow服务"""
        self.client = AsyncOpenAI(
            api_key=settings.SILICONFLOW_API_KEY,
            base_url=settings.SILICONFLOW_BASE_URL
        )
    
    async def generate(self, prompt: str, model: str = None, max_tokens: int = 1000) -> str:
        """生成文本
        
        Args:
            prompt: 提示词
            model: 模型名称
            max_tokens: 最大令牌数
            
        Returns:
            生成的文本
        """
        model = model or settings.SILICONFLOW_MODEL
        
        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": "你是一个专业的助手，根据用户的提示生成准确、有用的内容。"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=max_tokens,
                temperature=0.7
            )
            print(f"SiliconFlow API调用成功: {response.choices[0].message.content.strip()}")
            
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"SiliconFlow API调用失败: {e}")
            # 返回默认值
            return ""
