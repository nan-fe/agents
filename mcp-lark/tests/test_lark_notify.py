"""审核通过通知消息格式化测试。"""

from __future__ import annotations

import json

from lark_im.notify import (
    format_review_passed_markdown,
    markdown_to_post_content,
    text_message_content,
)


def test_format_review_passed_markdown_includes_key_fields() -> None:
    result = {
        "title": "测试标题",
        "content": "正文内容" * 50,
        "project_id": "proj_abc",
        "version": "v3",
        "version_id": "ver_xyz",
        "image_url": "https://example.com/img.png",
        "review_feedback": "语气自然",
    }
    md = format_review_passed_markdown(result)
    assert "✅ 内容审核通过" in md
    assert "测试标题" in md
    assert "proj_abc" in md
    assert "v3" in md
    assert "ver_xyz" in md
    assert "https://example.com/img.png" in md
    assert "语气自然" in md
    assert len(md) < len("正文内容" * 50) + 500


def test_markdown_to_post_content() -> None:
    content = markdown_to_post_content("## Hello", title="标题")
    parsed = json.loads(content)
    assert parsed["zh_cn"]["title"] == "标题"
    assert parsed["zh_cn"]["content"][0][0]["tag"] == "md"


def test_text_message_content() -> None:
    parsed = json.loads(text_message_content("hi"))
    assert parsed["text"] == "hi"
