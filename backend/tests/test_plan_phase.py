from app.agents.orchestrator.planning import (
    FRESH_TASK_INTENTS,
    is_fresh_task_intent,
    should_run_content_strategist,
)


def test_fresh_task_intents() -> None:
    assert FRESH_TASK_INTENTS == frozenset({"new_task", "change_topic"})


def test_is_fresh_task_intent() -> None:
    assert is_fresh_task_intent("new_task") is True
    assert is_fresh_task_intent("change_topic") is True
    assert is_fresh_task_intent("refine_content") is False
    assert is_fresh_task_intent("refine_image") is False
    assert is_fresh_task_intent("ask_question") is False


def test_should_run_content_strategist_fresh_task() -> None:
    assert should_run_content_strategist("new_task", has_last_plan=True) is True
    assert should_run_content_strategist("change_topic", has_last_plan=True) is True


def test_should_run_content_strategist_refine_reuses_plan() -> None:
    assert should_run_content_strategist("refine_content", has_last_plan=True) is False
    assert should_run_content_strategist("refine_image", has_last_plan=True) is False
    assert should_run_content_strategist("refine_content", has_last_plan=False) is True
