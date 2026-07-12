"""将创作结果适配为微博正文格式。"""

from __future__ import annotations

import re
from dataclasses import dataclass

_WEIBO_MAX_CHARS = 2000  # 微博长文上限；普通微博建议控制在更短范围
_X_MAX_CHARS = 280  # X 推文字符上限


@dataclass(frozen=True)
class WeiboPublishPayload:
    text: str
    image_url: str | None = None
    share_url: str | None = None


@dataclass(frozen=True)
class XPublishPayload:
    text: str
    image_url: str | None = None
    share_url: str | None = None


def _normalize_hashtag(tag: str) -> str:
    cleaned = (tag or "").strip().lstrip("#")
    return f"#{cleaned}" if cleaned else ""


def format_weibo_text(
    *,
    title: str = "",
    content: str = "",
    hashtags: list[str] | None = None,
    share_url: str | None = None,
    max_chars: int = _WEIBO_MAX_CHARS,
) -> str:
    """合并标题、正文、话题与分享链接为微博正文。"""
    parts: list[str] = []
    title_text = (title or "").strip()
    body = (content or "").strip()
    if title_text and body:
        parts.append(f"{title_text}\n\n{body}")
    elif title_text:
        parts.append(title_text)
    elif body:
        parts.append(body)

    tags = [_normalize_hashtag(t) for t in (hashtags or [])]
    tags = [t for t in tags if t]
    if tags:
        parts.append(" ".join(tags))

    share = (share_url or "").strip()
    if share:
        parts.append(share)

    text = "\n\n".join(p for p in parts if p).strip()
    if len(text) <= max_chars:
        return text

    # 超长时优先保留标题与开头正文，末尾附省略提示
    suffix = "…（全文见分享链接）"
    if share and share not in suffix:
        budget = max_chars - len(suffix) - len(share) - 2
        if budget > 40:
            truncated = text[:budget].rstrip() + suffix + f"\n\n{share}"
            return truncated[:max_chars]
    return text[: max_chars - 1] + "…"


def build_weibo_payload(
    *,
    title: str = "",
    content: str = "",
    hashtags: list[str] | None = None,
    image_url: str | None = None,
    share_url: str | None = None,
) -> WeiboPublishPayload:
    image = (image_url or "").strip() or None
    return WeiboPublishPayload(
        text=format_weibo_text(
            title=title,
            content=content,
            hashtags=hashtags,
            share_url=share_url,
        ),
        image_url=image,
        share_url=(share_url or "").strip() or None,
    )


def format_x_text(
    *,
    title: str = "",
    content: str = "",
    hashtags: list[str] | None = None,
    share_url: str | None = None,
    max_chars: int = _X_MAX_CHARS,
) -> str:
    """合并标题、正文、话题与分享链接为 X 推文（280 字符上限）。"""
    parts: list[str] = []
    title_text = (title or "").strip()
    body = (content or "").strip()
    if title_text and body:
        parts.append(f"{title_text}\n\n{body}")
    elif title_text:
        parts.append(title_text)
    elif body:
        parts.append(body)

    tags = [_normalize_hashtag(t) for t in (hashtags or [])]
    tags = [t for t in tags if t]
    if tags:
        parts.append(" ".join(tags))

    share = (share_url or "").strip()
    if share:
        parts.append(share)

    text = "\n\n".join(p for p in parts if p).strip()
    if len(text) <= max_chars:
        return text

    suffix = "…"
    if share:
        budget = max_chars - len(suffix) - len(share) - 2
        if budget > 20:
            truncated = text[:budget].rstrip() + suffix + f"\n{share}"
            return truncated[:max_chars]
    return text[: max_chars - len(suffix)] + suffix


def _x_safe_max_chars(*, has_image: bool = False) -> int:
    # 留少量余量，避免 X 计数与 Python len 不一致导致按钮禁用
    return 80 if has_image else 80


def build_x_payload(
    *,
    title: str = "",
    content: str = "",
    hashtags: list[str] | None = None,
    image_url: str | None = None,
    share_url: str | None = None,
) -> XPublishPayload:
    image = (image_url or "").strip() or None
    return XPublishPayload(
        text=format_x_text(
            title=title,
            content=content,
            hashtags=hashtags,
            share_url=share_url,
            max_chars=_x_safe_max_chars(has_image=bool(image)),
        ),
        image_url=image,
        share_url=(share_url or "").strip() or None,
    )


def is_likely_logged_in_url(url: str) -> bool:
    """启发式：当前页面是否像已登录的微博首页。"""
    lowered = (url or "").lower()
    logged_out_markers = (
        "passport.weibo.com",
        "login.sina.com.cn",
        "newlogin",
        "/login",
        "/sorry",
    )
    if any(marker in lowered for marker in logged_out_markers):
        return False
    return "weibo.com" in lowered


def extract_tweet_id_from_url(url: str) -> str | None:
    """从 X/Twitter 状态 URL 提取 tweet id。"""
    m = re.search(r"/status/(\d+)", url or "")
    return m.group(1) if m else None
