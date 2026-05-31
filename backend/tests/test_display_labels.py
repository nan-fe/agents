from app.utils.display_labels import (
    agent_display_label,
    format_agent_pipeline,
    intent_display_label,
)


def test_intent_display_label():
    assert intent_display_label("new_task") == "新创作任务"
    assert intent_display_label("unknown") == "unknown"


def test_agent_display_label():
    assert agent_display_label("CopywriterAgent") == "文案"
    assert agent_display_label("ContentStrategist") == "内容策划"
    assert agent_display_label("Orchestrator") == "编排"


def test_format_agent_pipeline():
    assert format_agent_pipeline(
        ["CopywriterAgent", "ImageAgent", "ReviewerAgent"]
    ) == ["文案", "配图", "审核"]
