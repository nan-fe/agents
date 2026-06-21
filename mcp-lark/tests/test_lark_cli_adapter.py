"""lark-cli 适配层测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from lark_im.lark_cli_adapter import LarkCliAdapter, should_use_lark_cli


def test_should_use_lark_cli_auto_without_app_credentials() -> None:
    with patch(
        "lark_im.lark_cli_adapter.lark_cli_available",
        return_value=True,
    ):
        with patch(
            "lark_im.lark_cli_adapter.lark_settings.LARK_USE_CLI",
            None,
        ):
            with patch(
                "lark_im.lark_cli_adapter.lark_settings.LARK_APP_ID",
                "",
            ):
                with patch(
                    "lark_im.lark_cli_adapter.lark_settings.LARK_APP_SECRET",
                    "",
                ):
                    with patch(
                        "lark_im.lark_cli_adapter.lark_settings.LARK_USER_ACCESS_TOKEN",
                        "",
                    ):
                        assert should_use_lark_cli() is True


@pytest.mark.asyncio
async def test_cli_send_message() -> None:
    adapter = LarkCliAdapter(cli_path="lark-cli")
    with patch.object(
        adapter,
        "_run",
        new=AsyncMock(return_value={"data": {"message_id": "om_cli"}}),
    ):
        result = await adapter.send_message(
            "oc_test",
            text="hello",
            identity="user",
        )
    assert result["message_id"] == "om_cli"
