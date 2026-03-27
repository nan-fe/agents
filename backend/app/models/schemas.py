from pydantic import BaseModel
from typing import Optional, List


class UserInput(BaseModel):
    """用户输入模型"""
    prompt: str


class AgentLog(BaseModel):
    """Agent日志模型"""
    agent_name: str
    message: str
    timestamp: float


class ProductRecommendation(BaseModel):
    """商品推荐模型"""
    product_name: str
    description: str
    taobao_link: str
    price: Optional[str] = None


class PlanningResult(BaseModel):
    """策划Agent输出模型"""
    target_audience: List[str]
    core_selling_points: List[str]
    tone_style: str
    image_requirements: str
    product_category: str
    product_recommendations: Optional[List[ProductRecommendation]] = None


class CopywritingResult(BaseModel):
    """文案Agent输出模型"""
    title: str
    content: str
    hashtags: List[str]


class ImageResult(BaseModel):
    """图片Agent输出模型"""
    image_url: str
    prompt: str


class ReviewResult(BaseModel):
    """质检Agent输出模型"""
    approved: bool
    feedback: Optional[str] = None
    corrections: Optional[dict] = None


class FinalResult(BaseModel):
    """最终结果模型"""
    title: str
    content: str
    hashtags: List[str]
    image_url: str
    product_recommendations: Optional[List[ProductRecommendation]] = None


class SSEMessage(BaseModel):
    """SSE消息模型"""
    type: str  # 'log' or 'result'
    data: Optional[dict] = None
