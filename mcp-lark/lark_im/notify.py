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


_LARK_PROMPT_DEFAULT = "审核已通过。是否推送到飞书？"


def is_lark_notify_configured() -> bool:
    """是否已配置 OpenAPI Bot 推送所需的应用凭证与通知群。"""
    from lark_im.settings import lark_settings

    app_id = (lark_settings.LARK_APP_ID or "").strip()
    secret = (lark_settings.LARK_APP_SECRET or "").strip()
    chat_id = (lark_settings.LARK_NOTIFY_CHAT_ID or "").strip()
    return bool(app_id and secret and chat_id)


def build_lark_notification_meta(
    *,
    review_passed: bool,
    auto_sent: bool = False,
    error: str | None = None,
) -> dict[str, Any]:
    """构建 SSE/API 结果中的 lark_notification 元数据。"""
    from lark_im.settings import lark_settings

    mode = (lark_settings.LARK_NOTIFY_MODE or "auto").strip().lower()
    if mode not in {"auto", "prompt", "off"}:
        mode = "auto"

    return {
        "eligible": review_passed,
        "mode": mode,
        "configured": is_lark_notify_configured(),
        "auto_sent": auto_sent,
        "error": error,
        "prompt": _LARK_PROMPT_DEFAULT,
    }
