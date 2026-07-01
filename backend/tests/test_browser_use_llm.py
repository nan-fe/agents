"""browser-use LLM 配置测试。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.config import settings
from app.services.social.browser_use_fallback import (
    _resolve_browser_use_model,
    create_browser_use_llm,
)


def test_resolve_browser_use_model_defaults_to_base() -> None:
    with patch.object(settings, "BROWSER_USE_LLM_MODEL", ""):
        with patch.object(settings, "BASE_MODEL", "deepseek-v4-flash"):
            assert _resolve_browser_use_model() == "deepseek-v4-flash"


def test_resolve_browser_use_model_override() -> None:
    with patch.object(settings, "BROWSER_USE_LLM_MODEL", "Qwen/Qwen3-8B"):
        assert _resolve_browser_use_model() == "Qwen/Qwen3-8B"


def test_create_browser_use_llm_uses_project_endpoint() -> None:
    mock_llm = MagicMock(
        model="deepseek-v4-flash",
        base_url="https://token.sensenova.cn/v1",
        api_key="test-key",
    )
    with patch.object(settings, "API_KEY", "test-key"):
        with patch.object(settings, "MODEL_BASE_URL", "https://token.sensenova.cn/v1"):
            with patch.object(settings, "BASE_MODEL", "deepseek-v4-flash"):
                with patch.object(settings, "BROWSER_USE_LLM_MODEL", ""):
                    with patch(
                        "browser_use.llm.openai.chat.ChatOpenAI",
                        create=True,
                        return_value=mock_llm,
                    ) as mock_chat_openai:
                        llm = create_browser_use_llm()
    mock_chat_openai.assert_called_once_with(
        model="deepseek-v4-flash",
        api_key="test-key",
        base_url="https://token.sensenova.cn/v1",
        temperature=0.2,
    )
    assert llm.model == "deepseek-v4-flash"
    assert str(llm.base_url) == "https://token.sensenova.cn/v1"
    assert llm.api_key == "test-key"
