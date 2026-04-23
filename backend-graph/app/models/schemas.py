from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class PlanStep(BaseModel):
    """计划步骤"""
    step_name: str
    agent: str
    description: str
    priority: int


class PlanningResult(BaseModel):
    """策划结果"""
    topic: str = Field(..., description="主题")
    target_audience: List[str] = Field(..., description="目标人群")
    core_selling_points: List[str] = Field(..., description="核心卖点")
    tone_style: str = Field(..., description="语气风格")
    image_requirements: str = Field(..., description="图片需求")
    product_category: str = Field(..., description="产品类别")
    product_recommendations: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="产品推荐")


class CopywritingResult(BaseModel):
    """文案结果"""
    title: str = Field(..., description="标题")
    content: str = Field(..., description="内容")
    hashtags: List[str] = Field(..., description="标签")


class ImageResult(BaseModel):
    """图片结果"""
    image_url: str = Field(..., description="图片URL")
    prompt: str = Field(..., description="图片提示词")


class ReviewResult(BaseModel):
    """审核结果"""
    approved: bool = Field(..., description="是否通过")
    feedback: str = Field(..., description="反馈")


class RoutingDecision(BaseModel):
    """路由决策"""
    agents_to_call: List[str] = Field(..., description="要调用的Agent")
    priority_order: List[str] = Field(..., description="优先级顺序")
    reasoning: str = Field(..., description="决策理由")


class RetryDecision(BaseModel):
    """重试决策"""
    should_retry: bool = Field(..., description="是否重试")
    action_type: str = Field(..., description="行动类型")
    target_agent: Optional[str] = Field(None, description="目标Agent")
    modified_params: Optional[Dict[str, Any]] = Field(None, description="修改的参数")
    reasoning: str = Field(..., description="决策理由")


class UserInput(BaseModel):
    """用户输入"""
    prompt: str = Field(..., description="提示词")
    session_id: Optional[str] = Field(None, description="会话ID")


class SSEMessage(BaseModel):
    """SSE消息"""
    type: str = Field(..., description="消息类型")
    data: Dict[str, Any] = Field(..., description="消息数据")


class GraphState(BaseModel):
    """LangGraph 状态"""
    user_input: str = ""
    session_id: Optional[str] = None
    planning: Dict[str, Any] = Field(default_factory=dict)
    rag_context: Optional[Any] = None
    copywriting: Dict[str, Any] = Field(default_factory=dict)
    image: Dict[str, Any] = Field(default_factory=dict)
    review: Dict[str, Any] = Field(default_factory=dict)
    final_result: Dict[str, Any] = Field(default_factory=dict)
    routing_decision: Optional[RoutingDecision] = None
    current_agent: Optional[str] = None
    agent_outputs: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None