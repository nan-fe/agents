"""规划阶段共享意图常量与规则。"""

FRESH_TASK_INTENTS = frozenset({"new_task", "change_topic"})
REFINE_INTENTS = frozenset({"refine_content", "refine_image"})

PIPELINE_BY_INTENT: dict[str, list[str]] = {
    "refine_content": ["CopywriterAgent", "ReviewerAgent"],
    "refine_image": ["ImageAgent", "ReviewerAgent"],
}

FULL_PIPELINE = ["CopywriterAgent", "ImageAgent", "ReviewerAgent"]


def is_fresh_task_intent(intent: str) -> bool:
    """新任务 / 换题：重新策划，不复用上一轮 plan 与 result。"""
    return intent in FRESH_TASK_INTENTS


def should_run_content_strategist(intent: str, has_last_plan: bool) -> bool:
    """是否在本轮执行 ContentStrategistAgent。"""
    if is_fresh_task_intent(intent):
        return True
    if intent in REFINE_INTENTS:
        return not has_last_plan
    return not has_last_plan
