"""审核通过等通知的消息格式化。"""

from __future__ import annotations

import json
from typing import Any

_CONTENT_PREVIEW_MAX = 200


def _truncate(text: str, max_len: int) -> str:
    stripped = (text or "").strip()
    if len(stripped) <= max_len:
        return stripped
    return stripped[: max_len - 1] + "…"


def format_review_passed_markdown(result: dict[str, Any]) -> str:
    """将生成结果格式化为 Markdown 文本（用于 post/md 消息）。"""
    title = _truncate(str(result.get("title") or "（无标题）"), 80)
    content = _truncate(str(result.get("content") or ""), _CONTENT_PREVIEW_MAX)
    project_id = str(result.get("project_id") or "").strip()
    version = str(result.get("version") or "").strip()
    version_id = str(result.get("version_id") or "").strip()
    image_url = str(result.get("image_url") or "").strip()
    feedback = str(result.get("review_feedback") or "").strip()

    lines = [
        "## ✅ 内容审核通过",
        "",
        f"**标题**：{title}",
        "",
        "**正文摘要**：",
        content or "（无正文）",
        "",
        "**项目信息**：",
        f"- project_id: `{project_id}`" if project_id else "- project_id: （未知）",
    ]
    if version:
        lines.append(f"- version: `{version}`")
    if version_id:
        lines.append(f"- version_id: `{version_id}`")
    if image_url:
        lines.append(f"- 配图: {image_url}")
    if feedback:
        lines.append("")
        lines.append(f"**审核备注**：{feedback}")

    return "\n".join(lines)


def markdown_to_post_content(markdown: str, title: str | None = None) -> str:
    """将 Markdown 转为飞书 post 消息 content JSON 字符串。"""
    post: dict[str, Any] = {
        "zh_cn": {
            "content": [[{"tag": "md", "text": markdown}]],
        }
    }
    if title:
        post["zh_cn"]["title"] = title
    return json.dumps(post, ensure_ascii=False)


def text_message_content(text: str) -> str:
    return json.dumps({"text": text}, ensure_ascii=False)
