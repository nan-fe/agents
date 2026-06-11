from langchain_core.messages import HumanMessage

from app.agents.orchestrator.session_history import WritingSessionHistory


def test_session_history_messages_and_state() -> None:
    history = WritingSessionHistory("session-1")
    history.add_message(HumanMessage(content="写一篇防晒文案"))
    history.add_message(HumanMessage(content="再改短一点"))

    assert len(history.get_messages()) == 2
    assert history.get_last_result() is None
    assert history.get_last_plan() is None

    history.update_result({"title": "标题", "content": "正文", "hashtags": ["#防晒"]})
    history.update_plan({"topic": "防晒", "tone_style": "亲切"})

    assert history.get_last_result()["title"] == "标题"
    assert history.get_last_plan()["topic"] == "防晒"

    history.bind_project("proj_test123")
    history.bind_version("ver_abc", "v2")
    assert history.project_id == "proj_test123"
    assert history.current_version_id == "ver_abc"
    assert history.current_version_label == "v2"

    history.clear()
    assert history.get_messages() == []
    assert history.get_last_result() is None
    assert history.get_last_plan() is None
