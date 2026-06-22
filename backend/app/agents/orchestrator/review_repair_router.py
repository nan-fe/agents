"""审核失败后的规则路由（不调用 LLM）。"""

from typing import Any, Dict, List

CONTENT_AGENTS = frozenset({"CopywriterAgent", "ImageAgent"})

NON_REPAIR_CATEGORIES = frozenset({"policy_block", "review_error"})


def content_agents_ran(executed_agents: List[str]) -> bool:
    """是否执行过文案或配图类 Agent。"""
    return bool(CONTENT_AGENTS & set(executed_agents))


def derive_failure_category(
    failure_category: str | None,
    feedback: str,
    corrections: Dict[str, Any] | None,
) -> str:
    """从 LLM 字段或 corrections 键兜底推导失败域。"""
    if failure_category:
        return failure_category

    corr = corrections or {}
    has_copy = bool(corr.get("copywriting"))
    has_image = bool(corr.get("image"))
    if has_copy and has_image:
        return "both"
    if has_copy:
        return "copywriting"
    if has_image:
        return "image"

    text = (feedback or "").lower()
    image_keywords = ("图片", "配图", "image", "prompt", "构图", "美观")
    policy_keywords = ("违规", "违法", "不可", "禁止", "policy")
    if any(k in text for k in image_keywords):
        return "image"
    if any(k in text for k in policy_keywords):
        return "policy_block"
    return "copywriting"


def route_review_failure(
    failure_category: str | None,
    feedback: str,
    corrections: Dict[str, Any] | None,
    partial_errors: Dict[str, str] | None = None,
    image_repair_attempts: int = 0,
) -> List[str]:
    """根据审核失败类型返回 repair 流水线 Agent 列表；空列表表示不 repair。"""
    category = derive_failure_category(failure_category, feedback, corrections)
    if category in NON_REPAIR_CATEGORIES:
        return []

    partial_errors = partial_errors or {}

    if category == "copywriting":
        return ["CopywriterAgent", "ReviewerAgent"]

    if category == "image":
        if partial_errors.get("ImageAgent") and image_repair_attempts >= 1:
            return []
        return ["ImageAgent", "ReviewerAgent"]

    if category == "both":
        if partial_errors.get("ImageAgent") and image_repair_attempts >= 1:
            return ["CopywriterAgent", "ReviewerAgent"]
        return ["CopywriterAgent", "ImageAgent", "ReviewerAgent"]

    return []
