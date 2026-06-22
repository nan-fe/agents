"""LarkImService 单元测试（mock HTTP）。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lark_im.client import LarkClient
from lark_im.im_service import LarkImService


@pytest.fixture
def mock_client() -> MagicMock:
    client = MagicMock(spec=LarkClient)
    client.get_auth_status = AsyncMock(
        return_value={
            "bot": {"configured": True, "available": True, "error": None},
            "user": {"configured": False, "available": False, "error": "x"},
            "default_identity": "bot",
        }
    )
    client.request = AsyncMock(return_value={"code": 0, "data": {"message_id": "om_test"}})
    return client


@pytest.mark.asyncio
async def test_send_message_text(mock_client: MagicMock) -> None:
    service = LarkImService(client=mock_client, use_cli=False)
    result = await service.send_message("oc_chat", text="hello")
    assert result["message_id"] == "om_test"
    mock_client.request.assert_awaited_once()
    call_kwargs = mock_client.request.await_args.kwargs
    assert call_kwargs["json_body"]["receive_id"] == "oc_chat"
    assert call_kwargs["json_body"]["msg_type"] == "text"


@pytest.mark.asyncio
async def test_send_message_markdown(mock_client: MagicMock) -> None:
    service = LarkImService(client=mock_client, use_cli=False)
    await service.send_message("oc_chat", markdown="## Title")
    call_kwargs = mock_client.request.await_args.kwargs
    assert call_kwargs["json_body"]["msg_type"] == "post"


@pytest.mark.asyncio
async def test_send_review_notification(mock_client: MagicMock) -> None:
    with patch(
        "lark_im.im_service.lark_settings.LARK_NOTIFY_CHAT_ID",
        "oc_notify",
    ):
        service = LarkImService(client=mock_client, use_cli=False)
        await service.send_review_notification({"title": "t", "content": "c"})
        call_kwargs = mock_client.request.await_args.kwargs
        assert call_kwargs["json_body"]["receive_id"] == "oc_notify"


@pytest.mark.asyncio
async def test_tenant_token_cached() -> None:
    client = LarkClient(app_id="id", app_secret="secret")

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "code": 0,
        "tenant_access_token": "tok_1",
        "expire": 7200,
    }

    mock_http = MagicMock()
    mock_http.post = AsyncMock(return_value=mock_response)
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=mock_http):
        token1 = await client._get_tenant_access_token()
        token2 = await client._get_tenant_access_token()

    assert token1 == "tok_1"
    assert token2 == "tok_1"
    assert mock_http.post.await_count == 1
