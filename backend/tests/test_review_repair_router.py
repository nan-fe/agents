from app.agents.orchestrator.review_repair_router import (
    content_agents_ran,
    derive_failure_category,
    route_review_failure,
)


def test_content_agents_ran() -> None:
    assert content_agents_ran(["CopywriterAgent"]) is True
    assert content_agents_ran(["RagAgent", "ContentStrategistAgent"]) is False


def test_derive_failure_category_from_corrections() -> None:
    assert (
        derive_failure_category(None, "", {"copywriting": {"content": "改"}})
        == "copywriting"
    )
    assert derive_failure_category(None, "", {"image": {"prompt": "改"}}) == "image"
    assert (
        derive_failure_category(
            None,
            "",
            {"copywriting": {"content": "a"}, "image": {"prompt": "b"}},
        )
        == "both"
    )


def test_derive_failure_category_policy_keywords() -> None:
    assert derive_failure_category(None, "内容违规不可发布", None) == "policy_block"


def test_route_review_failure_copywriting() -> None:
    agents = route_review_failure("copywriting", "标题夸大", None)
    assert agents == ["CopywriterAgent", "ReviewerAgent"]


def test_route_review_failure_no_repair_for_policy() -> None:
    assert route_review_failure("policy_block", "违规", None) == []
    assert route_review_failure("review_error", "审核失败", None) == []


def test_route_review_failure_image_skips_after_partial_error() -> None:
    agents = route_review_failure(
        "image",
        "配图问题",
        None,
        partial_errors={"ImageAgent": "TIMEOUT"},
        image_repair_attempts=1,
    )
    assert agents == []


def test_route_review_failure_both_degrades_when_image_exhausted() -> None:
    agents = route_review_failure(
        "both",
        "都有问题",
        None,
        partial_errors={"ImageAgent": "TIMEOUT"},
        image_repair_attempts=1,
    )
    assert agents == ["CopywriterAgent", "ReviewerAgent"]
