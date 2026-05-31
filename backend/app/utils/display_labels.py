"""意图与 Agent 展示名映射，供 SSE 日志与前端展示。"""
from typing import Dict, Iterable, List

INTENT_DISPLAY_LABELS: Dict[str, str] = {
    "new_task": "新创作任务",
    "refine_content": "优化文案",
    "refine_image": "重新配图",
    "change_topic": "更换主题",
    "ask_question": "问答",
    "review_failure": "审核未通过，自动修复",
}

AGENT_DISPLAY_LABELS: Dict[str, str] = {
    "Orchestrator": "编排",
    "SafetyGuard": "安全审核",
    "PlannerAgent": "策划",
    "Planner": "策划",
    "CopywriterAgent": "文案",
    "Copywriter": "文案",
    "ImageAgent": "配图",
    "Image Designer": "配图",
    "ReviewerAgent": "审核",
    "Reviewer": "审核",
    "RagAgent": "商品检索",
}


def intent_display_label(intent: str) -> str:
    return INTENT_DISPLAY_LABELS.get(intent, intent)


def agent_display_label(agent_key: str) -> str:
    return AGENT_DISPLAY_LABELS.get(agent_key, agent_key)


def format_agent_pipeline(agent_keys: Iterable[str]) -> List[str]:
    return [agent_display_label(key) for key in agent_keys]


def display_label_maps() -> Dict[str, Dict[str, str]]:
    return {
        "intent_labels": dict(INTENT_DISPLAY_LABELS),
        "agent_labels": dict(AGENT_DISPLAY_LABELS),
    }
