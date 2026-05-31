from app.services.orchestrator_llm_service import _routing_intent_guidance


def test_routing_intent_guidance_fresh_only() -> None:
    assert "完整" in _routing_intent_guidance("new_task")
    assert "完整" in _routing_intent_guidance("change_topic")
    assert "CopywriterAgent" not in _routing_intent_guidance("refine_content")
