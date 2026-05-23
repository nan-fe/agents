from app.agents.orchestrator.agent import FRESH_TASK_INTENTS, is_fresh_task_intent


def test_fresh_task_intents() -> None:
    assert FRESH_TASK_INTENTS == frozenset({"new_task", "change_topic"})


def test_is_fresh_task_intent() -> None:
    assert is_fresh_task_intent("new_task") is True
    assert is_fresh_task_intent("change_topic") is True
    assert is_fresh_task_intent("refine_content") is False
    assert is_fresh_task_intent("refine_image") is False
    assert is_fresh_task_intent("ask_question") is False
