"""飞书 IM 服务：发消息、回复、查群、读消息、审核通知。"""

from __future__ import annotations

from typing import Any, Literal

from lark_im.client import LarkClient, LarkIdentity
from lark_im.lark_cli_adapter import (
    LarkCliAdapter,
    LarkIdentityParam,
    should_use_lark_cli,
)
from lark_im.notify import (
    format_review_passed_markdown,
    markdown_to_post_content,
    text_message_content,
)
from lark_im.settings import lark_settings

_service: LarkImService | None = None


class LarkImService:
    """飞书即时消息能力封装（OpenAPI 或本机 lark-cli）。"""

    def __init__(
        self,
        client: LarkClient | None = None,
        cli_adapter: LarkCliAdapter | None = None,
        *,
        use_cli: bool | None = None,
    ) -> None:
        self._client = client or LarkClient()
        self._cli = cli_adapter or LarkCliAdapter()
        self._use_cli = (
            use_cli if use_cli is not None else should_use_lark_cli(self._client)
        )

    async def get_auth_status(self) -> dict[str, Any]:
        if self._use_cli:
            return await self._cli.get_auth_status()
        return await self._client.get_auth_status()

    def _resolve_identity(self, identity: LarkIdentityParam | None) -> LarkIdentity:
        if identity:
            return identity

        default = (lark_settings.LARK_DEFAULT_IDENTITY or "user").strip().lower()
        preferred: LarkIdentity = "user" if default == "user" else "bot"

        if self._use_cli:
            return preferred

        if preferred == "user" and self._client._can_user_auth():
            return "user"
        if preferred == "bot" and self._client._can_bot_auth():
            return "bot"
        if self._client._can_user_auth():
            return "user"
        if self._client._can_bot_auth():
            return "bot"
        return preferred

    def _resolve_cli_identity(
        self, identity: LarkIdentityParam | None
    ) -> LarkIdentityParam:
        resolved = self._resolve_identity(identity)
        return "user" if resolved == "user" else "bot"

    async def send_message(
        self,
        chat_id: str,
        text: str | None = None,
        markdown: str | None = None,
        *,
        identity: LarkIdentityParam | None = None,
    ) -> dict[str, Any]:
        receive_id = (chat_id or "").strip()
        if not receive_id:
            raise ValueError("chat_id 不能为空")

        if self._use_cli:
            return await self._cli.send_message(
                receive_id,
                text=text,
                markdown=markdown,
                identity=self._resolve_cli_identity(identity),
            )

        if markdown:
            msg_type = "post"
            content = markdown_to_post_content(markdown)
        elif text:
            msg_type = "text"
            content = text_message_content(text)
        else:
            raise ValueError("text 或 markdown 至少提供一个")

        resolved = self._resolve_identity(identity)
        data = await self._client.request(
            "POST",
            "/im/v1/messages",
            identity=resolved,
            params={"receive_id_type": "chat_id"},
            json_body={
                "receive_id": receive_id,
                "msg_type": msg_type,
                "content": content,
            },
        )
        return data.get("data") or {}

    async def reply_message(
        self,
        message_id: str,
        text: str | None = None,
        markdown: str | None = None,
        *,
        identity: LarkIdentityParam | None = None,
    ) -> dict[str, Any]:
        msg_id = (message_id or "").strip()
        if not msg_id:
            raise ValueError("message_id 不能为空")

        if self._use_cli:
            return await self._cli.reply_message(
                msg_id,
                text=text,
                markdown=markdown,
                identity=self._resolve_cli_identity(identity),
            )

        if markdown:
            msg_type = "post"
            content = markdown_to_post_content(markdown)
        elif text:
            msg_type = "text"
            content = text_message_content(text)
        else:
            raise ValueError("text 或 markdown 至少提供一个")

        resolved = self._resolve_identity(identity)
        data = await self._client.request(
            "POST",
            f"/im/v1/messages/{msg_id}/reply",
            identity=resolved,
            json_body={
                "msg_type": msg_type,
                "content": content,
            },
        )
        return data.get("data") or {}

    async def list_chat_messages(
        self,
        chat_id: str,
        *,
        page_size: int = 20,
        identity: LarkIdentityParam | None = None,
    ) -> dict[str, Any]:
        container_id = (chat_id or "").strip()
        if not container_id:
            raise ValueError("chat_id 不能为空")

        if self._use_cli:
            return await self._cli.list_chat_messages(
                container_id,
                page_size=page_size,
                identity=self._resolve_cli_identity(identity),
            )

        resolved = self._resolve_identity(identity)
        data = await self._client.request(
            "GET",
            "/im/v1/messages",
            identity=resolved,
            params={
                "container_id_type": "chat",
                "container_id": container_id,
                "page_size": min(max(page_size, 1), 50),
            },
        )
        return data.get("data") or {}

    async def search_chats(
        self,
        query: str,
        *,
        page_size: int = 20,
        identity: LarkIdentityParam | None = None,
    ) -> dict[str, Any]:
        keyword = (query or "").strip()
        if not keyword:
            raise ValueError("query 不能为空")

        if self._use_cli:
            return await self._cli.search_chats(
                keyword,
                page_size=page_size,
                identity=self._resolve_cli_identity(identity),
            )

        resolved = self._resolve_identity(identity)
        data = await self._client.request(
            "GET",
            "/im/v1/chats/search",
            identity=resolved,
            params={
                "query": keyword,
                "page_size": min(max(page_size, 1), 50),
            },
        )
        return data.get("data") or {}

    async def send_review_notification(
        self,
        result: dict[str, Any],
        *,
        chat_id: str | None = None,
        identity: LarkIdentityParam | None = None,
    ) -> dict[str, Any]:
        target_chat = (chat_id or lark_settings.LARK_NOTIFY_CHAT_ID or "").strip()
        if not target_chat:
            raise ValueError("LARK_NOTIFY_CHAT_ID 未配置")

        markdown = format_review_passed_markdown(result)
        return await self.send_message(
            target_chat,
            markdown=markdown,
            identity=identity,
        )


def get_lark_im_service() -> LarkImService:
    global _service
    if _service is None:
        _service = LarkImService()
    return _service
