"""content_adapter 单元测试。"""

from __future__ import annotations

from app.services.social.content_adapter import (
    build_weibo_payload,
    extract_tweet_id_from_url,
    format_weibo_text,
    is_likely_logged_in_url,
)


def test_format_weibo_text_merges_title_body_tags() -> None:
    text = format_weibo_text(
        title="标题",
        content="正文内容",
        hashtags=["测试", "#已有前缀"],
        share_url="https://example.com/share/abc",
    )
    assert "标题" in text
    assert "正文内容" in text
    assert "#测试" in text
    assert "#已有前缀" in text
    assert "https://example.com/share/abc" in text


def test_format_weibo_text_truncates_long_content() -> None:
    long_body = "长" * 3000
    text = format_weibo_text(content=long_body, max_chars=100)
    assert len(text) <= 100


def test_build_weibo_payload() -> None:
    payload = build_weibo_payload(title="T", content="C", image_url=" https://img.test/a.jpg ")
    assert payload.image_url == "https://img.test/a.jpg"
    assert "T" in payload.text
    assert "C" in payload.text


def test_is_likely_logged_in_url() -> None:
    assert is_likely_logged_in_url("https://weibo.com/home") is True
    assert is_likely_logged_in_url("https://passport.weibo.com/login") is False
    assert is_likely_logged_in_url("https://weibo.com/newlogin?tabtype=weibo") is False
    assert is_likely_logged_in_url("https://weibo.com/sorry?usernotexists") is False


def test_extract_tweet_id_from_url() -> None:
    assert extract_tweet_id_from_url("https://x.com/user/status/1234567890") == "1234567890"
    assert extract_tweet_id_from_url("https://example.com") is None
