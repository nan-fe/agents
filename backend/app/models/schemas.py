from datetime import datetime
from pydantic import BaseModel, Field
from typing import Literal, Optional, List

ReviewFailureCategory = Literal[
    "copywriting",
    "image",
    "both",
    "policy_block",
    "review_error",
]


class UserInput(BaseModel):
    """用户输入模型"""

    prompt: str
    session_id: str
    last_event_id: Optional[str] = None


class PlanningResult(BaseModel):
    """策划Agent输出模型"""

    target_audience: List[str]
    core_selling_points: List[str]
    tone_style: str
    image_requirements: str
    topic: str
    product_category: str


class ImageAgentInput(PlanningResult):
    copywriting_content: str
    user_input: str


class CopywritingResult(BaseModel):
    """文案Agent输出模型"""

    title: str
    content: str
    hashtags: List[str] = Field(default_factory=list)


class ImageResult(BaseModel):
    """图片Agent输出模型"""

    image_url: str
    prompt: str


class ReviewCorrections(BaseModel):
    """审核修改建议（结构化）"""

    copywriting: Optional[dict] = None
    image: Optional[dict] = None


class ReviewResult(BaseModel):
    """质检Agent输出模型"""

    approved: bool
    feedback: Optional[str] = None
    corrections: Optional[ReviewCorrections] = None
    failure_category: Optional[ReviewFailureCategory] = None


class ShareCreateRequest(BaseModel):
    """创建公开分享快照的请求"""

    title: str = ""
    content: str = ""
    hashtags: List[str] = Field(default_factory=list)
    image_url: Optional[str] = None
    message: Optional[str] = None


class ShareSnapshot(ShareCreateRequest):
    """公开分享快照"""

    id: str
    created_at: datetime
    expires_at: Optional[datetime] = None


class ShareCreateResponse(BaseModel):
    """创建分享后的响应"""

    share_id: str
    share: ShareSnapshot


class SSEMessage(BaseModel):
    """SSE消息模型"""

    type: str  # 'log' or 'result'
    data: Optional[dict] = None
