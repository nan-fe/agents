import os
from pathlib import Path
from typing import Tuple

import tiktoken

_TIKTOKEN_CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "tiktoken"


def _configure_tiktoken_cache() -> None:
    """Use project-local tiktoken cache to avoid network fetch at import time."""
    os.environ.setdefault("TIKTOKEN_CACHE_DIR", str(_TIKTOKEN_CACHE_DIR))


class TokenCounter:
    """Token计数器 - 精简版"""

    def __init__(self):
        # 模型配置
        self.models_config = {
            "sensenova-u1": {
                "context_window": 256000,  # 资源限制
                "max_output": 64000,  # 物理限制
            },
            "sensenova-u1-fast": {
                "context_window": 256000,
                "max_output": 64000,
            },
            "default": {
                "context_window": 256000,
                "max_output": 64000,  # 默认不限制
            },
        }

        # 编码器（所有模型都用 cl100k_base）
        _configure_tiktoken_cache()
        self.encoder = tiktoken.get_encoding("cl100k_base")

    def count_tokens(self, text: str) -> int:
        """计算文本token数"""
        return len(self.encoder.encode(text))

    def is_input_valid(
        self, input_tokens: int, model_name: str = "default", safety_buffer: int = 200
    ) -> Tuple[bool, int, int]:
        """判断输入是否有效

        Returns:
            (是否有效, 总上下文窗口, 最大允许输入)
        """
        config = self.models_config.get(model_name, self.models_config["default"])
        # 最大允许输入 = 总窗口 - 安全缓冲
        max_allowed_input = config["context_window"] - safety_buffer

        is_valid = input_tokens <= max_allowed_input

        return is_valid, config["context_window"], max_allowed_input

    def calculate_max_tokens(
        self, input_tokens: int, model_name: str = "default", safety_buffer: int = 200
    ) -> int:
        """计算最大输出token数"""
        config = self.models_config.get(model_name, self.models_config["default"])

        # 上下文余量 = 总窗口 - 输入 - 安全缓冲
        available_by_context = config["context_window"] - input_tokens - safety_buffer

        # ⭐ 关键：取上下文余量和模型输出上限的较小值
        max_tokens = min(available_by_context, config["max_output"])

        # 确保在合法范围内
        max_tokens = max(1, min(max_tokens, config["max_output"]))

        return max_tokens


# 全局实例
token_counter = TokenCounter()
