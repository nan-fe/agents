"""通过本地 lark-cli 调用飞书 IM（适合个人账号，无需自建企业应用凭证）。"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
from typing import Any, Literal

from lark_im.settings import lark_settings

logger = logging.getLogger(__name__)

LarkIdentityParam = Literal["bot", "user"]


class LarkCliError(Exception):
    """lark-cli 执行失败。"""


def lark_cli_available(cli_path: str | None = None) -> bool:
    path = (cli_path or lark_settings.LARK_CLI_PATH or "lark-cli").strip()
    return bool(path and shutil.which(path))


def should_use_lark_cli(client: Any | None = None) -> bool:
    """是否通过 lark-cli 发消息（个人账号默认路径）。"""
    if lark_settings.LARK_USE_CLI is not None:
        return lark_settings.LARK_USE_CLI

    if not lark_cli_available():
        return False

    has_app = bool(
        (lark_settings.LARK_APP_ID or "").strip() and (lark_settings.LARK_APP_SECRET or "").strip()
    )
    has_user_token = bool((lark_settings.LARK_USER_ACCESS_TOKEN or "").strip())

    return not has_app and not has_user_token


class LarkCliAdapter:
    """将 LarkImService 操作映射到 lark-cli 子命令。"""

    def __init__(self, cli_path: str | None = None) -> None:
        self._cli_path = (cli_path or lark_settings.LARK_CLI_PATH or "lark-cli").strip()

    async def _run(self, args: list[str]) -> dict[str, Any]:
        if not lark_cli_available(self._cli_path):
            raise LarkCliError(
                f"未找到 lark-cli（{self._cli_path}）。"
                "个人账号请先安装并执行 lark-cli config init 与 lark-cli auth login。"
            )

        cmd = [self._cli_path, *args, "--json"]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            err_text = (stderr or stdout).decode("utf-8", errors="replace").strip()
            raise LarkCliError(err_text or f"lark-cli 退出码 {proc.returncode}")

        raw = stdout.decode("utf-8", errors="replace").strip()
        if not raw:
            return {}

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"raw": raw}

    def _identity_flag(self, identity: LarkIdentityParam) -> list[str]:
        return ["--as", identity]

    async def get_auth_status(self) -> dict[str, Any]:
        data = await self._run(["auth", "status"])
        identities = data.get("identities") or {}
        bot = identities.get("bot") or {}
        user = identities.get("user") or {}
        return {
            "mode": "lark-cli",
            "bot": {
                "configured": bot.get("available", False),
                "available": bot.get("status") == "ready",
                "error": None if bot.get("available") else bot.get("message"),
            },
            "user": {
                "configured": user.get("available", False),
                "available": user.get("available", False),
                "error": None if user.get("available") else user.get("message"),
                "user_name": user.get("userName"),
            },
            "default_identity": lark_settings.LARK_DEFAULT_IDENTITY,
            "note": ("个人账号模式：通过本机 lark-cli 用户授权发消息，无需企业自建应用。"),
        }

    async def send_message(
        self,
        chat_id: str,
        text: str | None = None,
        markdown: str | None = None,
        *,
        identity: LarkIdentityParam = "user",
    ) -> dict[str, Any]:
        args = [
            "im",
            "+messages-send",
            "--chat-id",
            chat_id,
            *self._identity_flag(identity),
        ]
        if markdown:
            args.extend(["--markdown", markdown])
        elif text:
            args.extend(["--text", text])
        else:
            raise ValueError("text 或 markdown 至少提供一个")

        data = await self._run(args)
        return data.get("data") or data

    async def reply_message(
        self,
        message_id: str,
        text: str | None = None,
        markdown: str | None = None,
        *,
        identity: LarkIdentityParam = "user",
    ) -> dict[str, Any]:
        args = [
            "im",
            "+messages-reply",
            "--message-id",
            message_id,
            *self._identity_flag(identity),
        ]
        if markdown:
            args.extend(["--markdown", markdown])
        elif text:
            args.extend(["--text", text])
        else:
            raise ValueError("text 或 markdown 至少提供一个")

        data = await self._run(args)
        return data.get("data") or data

    async def list_chat_messages(
        self,
        chat_id: str,
        *,
        page_size: int = 20,
        identity: LarkIdentityParam = "user",
    ) -> dict[str, Any]:
        args = [
            "im",
            "+chat-messages-list",
            "--chat-id",
            chat_id,
            "--page-size",
            str(min(max(page_size, 1), 50)),
            *self._identity_flag(identity),
        ]
        data = await self._run(args)
        return data.get("data") or data

    async def search_chats(
        self,
        query: str,
        *,
        page_size: int = 20,
        identity: LarkIdentityParam = "user",
    ) -> dict[str, Any]:
        args = [
            "im",
            "+chat-search",
            "--query",
            query,
            "--page-size",
            str(min(max(page_size, 1), 50)),
            *self._identity_flag(identity),
        ]
        data = await self._run(args)
        return data.get("data") or data
