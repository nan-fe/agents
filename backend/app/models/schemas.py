from datetime import datetime
from typing import List, Literal

from pydantic import BaseModel, Field

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
    last_event_id: str | None = None
    project_id: str | None = None
    user_id: str | None = None


class ProjectFinalizeRequest(BaseModel):
    """页面关闭或新建话题时，将 versions 汇总写入 projects。"""

    project_id: str
    session_id: str | None = None
    user_id: str | None = None


class ProjectFinalizeResponse(BaseModel):
    project_id: str
    finalized: bool
    final_version: str | None = None
    version_count: int = 0
    message: str | None = None


class ProjectCreateRequest(BaseModel):
    user_id: str | None = None


class ProjectCreateResponse(BaseModel):
    project_id: str


class VersionSnapshot(BaseModel):
    version_id: str
    version_label: str
    version_number: int
    parent_version_id: str | None = None
    summary: str = ""
    user_input: str | None = None
    result: dict
    intent: str | None = None
    created_at: datetime


class ProjectConversationResponse(BaseModel):
    project_id: str
    topic: str | None = None
    final_version: str | None = None
    project_summary: str | None = None
    versions: List[VersionSnapshot] = Field(default_factory=list)


class ProjectListItem(BaseModel):
    project_id: str
    topic: str = ""
    final_version: str | None = None
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

    copywriting: dict | None = None
    image: dict | None = None


class ReviewResult(BaseModel):
    """质检Agent输出模型"""

    approved: bool
    feedback: str | None = None
    corrections: ReviewCorrections | None = None
    failure_category: ReviewFailureCategory | None = None


class ShareCreateRequest(BaseModel):
    """创建公开分享快照的请求"""

    title: str = ""
    content: str = ""
    hashtags: List[str] = Field(default_factory=list)
    image_url: str | None = None
    message: str | None = None


class ShareSnapshot(ShareCreateRequest):
    """公开分享快照"""

    id: str
    created_at: datetime
    expires_at: datetime | None = None


class ShareCreateResponse(BaseModel):
    """创建分享后的响应"""

    share_id: str
    share: ShareSnapshot


class SSEMessage(BaseModel):
    """SSE消息模型"""

    type: str  # 'log' or 'result'
    data: dict | None = None


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
    url: str | None = None
    cover_image: str | None = None
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

    title: str | None = None
    content: str | None = None
    project_id: str | None = None
    version: str | None = None
    version_id: str | None = None
    image_url: str | None = None
    review_feedback: str | None = None
    hashtags: List[str] | None = None
    user_id: str | None = None


class LarkStatusResponse(BaseModel):
    """飞书鉴权与通知配置状态。"""

    auth: dict
    notify_chat_configured: bool
    notify_enabled: bool
    notify_mode: str
    user_oauth: dict | None = None


class LarkOAuthRegisterRequest(BaseModel):
    """动态客户端注册（DCR）。"""

    client_name: str
    redirect_uris: List[str]
    scope: str | None = None


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


class WeiboPublishRequest(BaseModel):
    """触发微博自动发布。"""

    user_id: str = ""
    title: str | None = None
    content: str | None = None
    hashtags: List[str] | None = None
    image_url: str | None = None
    share_url: str | None = None
    review_approved: bool | None = None
    version_id: str | None = None


class WeiboPublishCreateResponse(BaseModel):
    job_id: str
    status: str = "pending"


class XPublishRequest(BaseModel):
    """触发 X 自动发布（Playwright Profile）。"""

    user_id: str = ""
    title: str | None = None
    content: str | None = None
    hashtags: List[str] | None = None
    image_url: str | None = None
    share_url: str | None = None
    review_approved: bool | None = None
    version_id: str | None = None


class XPublishCreateResponse(BaseModel):
    job_id: str
    status: str = "pending"


class XOAuthStartRequest(BaseModel):
    user_id: str


class WeiboOAuthStartRequest(BaseModel):
    user_id: str


class WeiboOAuthSessionResponse(BaseModel):
    session_id: str
    user_id: str
    logged_in: bool
    oauth_completed: bool = False
    oauth_error: str | None = None
    weibo_screen_name: str | None = None
    current_url: str
    profile_path: str
    viewport_width: int = 1280
    viewport_height: int = 900


class XOAuthSessionResponse(BaseModel):
    session_id: str
    user_id: str
    logged_in: bool
    oauth_completed: bool = False
    oauth_error: str | None = None
    x_username: str | None = None
    authorize_url: str = ""
    browserless: bool = False
    current_url: str
    profile_path: str
    viewport_width: int = 1280
    viewport_height: int = 900


class PublishJobResponse(BaseModel):
    job_id: str
    platform: str
    status: str
    progress: List[str] = Field(default_factory=list)
    post_url: str | None = None
    error: str | None = None
    screenshot_path: str | None = None
    created_at: float
    updated_at: float
    payload_summary: dict = Field(default_factory=dict)


class SocialStatusResponse(BaseModel):
    weibo_publish_enabled: bool
    weibo: dict
    weibo_oauth_configured: bool = False
    x_publish_enabled: bool = False
    x: dict = Field(default_factory=dict)
    x_oauth_configured: bool = False
    x_sync_enabled: bool
    x_sync_username: str | None = None
    x_sync_interval_seconds: int
    review_required: bool
    x_review_required: bool = True
    auto_on_complete: bool = True
    publish_engine: str = "playwright"
    x_publish_engine: str = "playwright"
    dry_run: bool
    x_dry_run: bool = False


class WeiboLoginStartResponse(BaseModel):
    session_id: str
    logged_in: bool
    current_url: str
    profile_path: str
    viewport_width: int = 1280
    viewport_height: int = 900


class WeiboLoginStatusResponse(BaseModel):
    session_id: str
    logged_in: bool
    current_url: str
    profile_path: str


HotspotPlatform = Literal["weibo", "xhs", "douyin", "x", "reddit"]
HotspotTrend = Literal["rising", "stable", "falling", "unknown"]

DEFAULT_HOTSPOT_PLATFORMS: list[str] = ["weibo", "xhs", "douyin", "x", "reddit"]
DEFAULT_HOTSPOT_KEYWORD = "商品宣传 营销 推广 种草 带货 品牌 新品 爆款"


class HotspotAnalyzeRequest(BaseModel):
    """社交媒体热点分析请求。"""

    keyword: str = Field(default=DEFAULT_HOTSPOT_KEYWORD, max_length=100)
    platforms: List[HotspotPlatform] = Field(
        default_factory=lambda: list(DEFAULT_HOTSPOT_PLATFORMS)
    )
    max_items_per_platform: int = Field(default=5, ge=1, le=5)
    locale: str = "zh-CN"


class HotspotItem(BaseModel):
    id: str
    platform: HotspotPlatform
    title: str
    summary: str
    promotion_relevance: str = ""
    heat_score: int = Field(ge=0, le=100)
    trend: HotspotTrend = "unknown"
    source_url: str
    published_at: str | None = None
    tags: List[str] = Field(default_factory=list)
    suspicious: bool = False


class TrendPoint(BaseModel):
    date: str
    count: int = Field(ge=0)
    avg_heat: float = Field(ge=0, le=100)


class PlatformStat(BaseModel):
    platform: HotspotPlatform
    count: int = Field(ge=0)
    avg_heat: float = Field(ge=0, le=100)


class HotspotAnalysisResult(BaseModel):
    keyword: str
    generated_at: datetime
    platforms: List[HotspotPlatform]
    summary: str
    hotspots: List[HotspotItem] = Field(default_factory=list)
    trend_series: List[TrendPoint] = Field(default_factory=list)
    platform_stats: List[PlatformStat] = Field(default_factory=list)
    cross_platform_hotspots: List[str] = Field(default_factory=list)
    marketing_insights: List[str] = Field(default_factory=list)
    data_source_notes: str = ""
    partial_errors: dict[str, str] = Field(default_factory=dict)
