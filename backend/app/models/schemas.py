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
    project_id: Optional[str] = None
    user_id: Optional[str] = None


class ProjectFinalizeRequest(BaseModel):
    """页面关闭或新建话题时，将 versions 汇总写入 projects。"""

    project_id: str
    session_id: Optional[str] = None
    user_id: Optional[str] = None


class ProjectFinalizeResponse(BaseModel):
    project_id: str
    finalized: bool
    final_version: Optional[str] = None
    version_count: int = 0
    message: Optional[str] = None


class ProjectCreateRequest(BaseModel):
    user_id: Optional[str] = None


class ProjectCreateResponse(BaseModel):
    project_id: str


class VersionSnapshot(BaseModel):
    version_id: str
    version_label: str
    version_number: int
    parent_version_id: Optional[str] = None
    summary: str = ""
    user_input: Optional[str] = None
    result: dict
    intent: Optional[str] = None
    created_at: datetime


class ProjectConversationResponse(BaseModel):
    project_id: str
    topic: Optional[str] = None
    final_version: Optional[str] = None
    project_summary: Optional[str] = None
    versions: List[VersionSnapshot] = Field(default_factory=list)


class ProjectListItem(BaseModel):
    project_id: str
    topic: str = ""
    final_version: Optional[str] = None
    project_summary: str = ""
    version_count: int = 0
    updated_at: datetime
    last_accessed_at: datetime
    finalized: bool = False


class ProjectListResponse(BaseModel):
    projects: List[ProjectListItem] = Field(default_factory=list)


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


class ProductInfoCreateRequest(BaseModel):
    """从商品链接创建选品池条目"""

    url: str = Field(min_length=8, description="淘宝/天猫/京东商品详情页链接")


class ProductInfoPreviewRequest(BaseModel):
    """识别商品链接中的信息（不入库）"""

    url: str = Field(min_length=8, description="淘宝/天猫/京东商品详情页链接")


class ProductInfoConfirmRequest(BaseModel):
    """确认将已识别的商品加入选品池"""

    preview_token: str = Field(min_length=8, description="预览接口返回的临时令牌")


class ProductComment(BaseModel):
    """商品评论摘要（预览展示用）"""

    content: str
    nickname: str = ""
    score: str = ""
    creation_time: str = ""


class ProductItem(BaseModel):
    """选品池商品条目"""

    id: str
    name: str
    category: str
    price: float
    description: str
    sales: int
    shop_name: str
    url: Optional[str] = None
    cover_image: Optional[str] = None
    comments: List[ProductComment] = Field(default_factory=list)


class ProductInfoCreateResponse(BaseModel):
    """创建商品后的响应"""

    product: ProductItem
    message: str = "商品已加入选品池并同步至检索索引"


class ProductInfoPreviewResponse(BaseModel):
    """商品链接识别预览（待用户确认）"""

    preview_token: str
    product: ProductItem
    message: str = "商品信息识别完成，请确认是否加入选品池"


class ProductListResponse(BaseModel):
    """选品池商品列表"""

    items: List[ProductItem]
    total: int


class LarkPushReviewRequest(BaseModel):
    """显式推送审核通过通知到飞书。"""

    title: Optional[str] = None
    content: Optional[str] = None
    project_id: Optional[str] = None
    version: Optional[str] = None
    version_id: Optional[str] = None
    image_url: Optional[str] = None
    review_feedback: Optional[str] = None
    hashtags: Optional[List[str]] = None
    user_id: Optional[str] = None


class LarkStatusResponse(BaseModel):
    """飞书鉴权与通知配置状态。"""

    auth: dict
    notify_chat_configured: bool
    notify_enabled: bool
    notify_mode: str
    user_oauth: Optional[dict] = None


class LarkOAuthRegisterRequest(BaseModel):
    """动态客户端注册（DCR）。"""

    client_name: str
    redirect_uris: List[str]
    scope: Optional[str] = None


class LarkOAuthRegisterResponse(BaseModel):
    client_id: str
    client_secret: str
    client_id_issued_at: int
    client_secret_expires_at: int = 0
    redirect_uris: List[str]
    scope: str
    grant_types: List[str] = ["authorization_code"]
    response_types: List[str] = ["code"]
    token_endpoint_auth_method: str = "none"
