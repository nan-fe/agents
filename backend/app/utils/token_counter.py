import tiktoken
from typing import Optional, List, Dict, Any, Tuple


class TokenCounter:
    """Token计数器"""

    def __init__(self):
        """初始化Token计数器"""
        # 映射模型到对应的编码
        self.encodings = {
            "gpt-3.5-turbo": "cl100k_base",
            "gpt-4": "cl100k_base",
            "gpt-4o": "cl100k_base",
            "deepseek-chat": "cl100k_base",
            "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B": "cl100k_base",
            "THUDM/GLM-Z1-9B-0414": "cl100k_base",
            "THUDM/GLM-4.1V-9B-Thinking": "cl100k_base",
            "Qwen/Qwen3-8B": "cl100k_base",
            "BAAI/bge-large-en-v1.5": "cl100k_base",
            "internlm/internlm2_5-7b-chat": "cl100k_base",
            "Kwai-Kolors/Kolors": "cl100k_base",
            "doubao-pro-1.5": "cl100k_base",
            "default": "cl100k_base",
        }

        # 模型上下文窗口大小（token）
        self.context_windows = {
            "gpt-3.5-turbo": 16384,
            "gpt-4": 8192,
            "gpt-4o": 128000,
            "deepseek-chat": 8192,
            "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B": 131072,  # 128K
            "THUDM/GLM-Z1-9B-0414": 131072,  # 128K
            "THUDM/GLM-4.1V-9B-Thinking": 65536,  # 64K
            "Qwen/Qwen3-8B": 131072,  # 128K
            "BAAI/bge-large-en-v1.5": 1024,  # 1K
            "internlm/internlm2_5-7b-chat": 32768,  # 32K
            "Kwai-Kolors/Kolors": 8192,  # 图片模型，使用默认值
            "doubao-pro-1.5": 8192,
            "default": 8192,
        }

        # 预留的回答空间（token）
        self.default_answer_reserve = 2000

    def get_encoding(self, model_name: str) -> tiktoken.Encoding:
        """获取对应模型的编码

        Args:
            model_name: 模型名称

        Returns:
            编码对象
        """
        encoding_name = self.encodings.get(model_name, self.encodings["default"])
        return tiktoken.get_encoding(encoding_name)

    def count_tokens(self, text: str, model_name: str = "default") -> int:
        """计算文本的token数

        Args:
            text: 要计算的文本
            model_name: 模型名称

        Returns:
            token数
        """
        encoding = self.get_encoding(model_name)
        return len(encoding.encode(text))

    def count_messages(
        self, messages: List[Dict[str, Any]], model_name: str = "default"
    ) -> int:
        """计算消息列表的token数

        Args:
            messages: 消息列表，格式为 [{"role": "user", "content": "..."}, ...]
            model_name: 模型名称

        Returns:
            token数
        """
        encoding = self.get_encoding(model_name)
        total_tokens = 0

        for message in messages:
            # 每条消息的开销
            total_tokens += 4  # 消息开始
            for key, value in message.items():
                if isinstance(value, str):
                    total_tokens += len(encoding.encode(value))
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict) and "text" in item:
                            total_tokens += len(encoding.encode(item["text"]))
            total_tokens += 2  # 消息结束

        total_tokens += 2  # 系统消息结束
        return total_tokens

    def get_context_window(self, model_name: str = "default") -> int:
        """获取模型的上下文窗口大小

        Args:
            model_name: 模型名称

        Returns:
            上下文窗口大小（token）
        """
        return self.context_windows.get(model_name, self.context_windows["default"])

    def calculate_available_space(
        self,
        history_tokens: int,
        current_question_tokens: int,
        model_name: str = "default",
        answer_reserve: Optional[int] = None,
    ) -> Tuple[int, int, int, int, bool]:
        """计算可用的上下文空间

        Args:
            history_tokens: 历史对话的token数
            current_question_tokens: 当前问题的token数
            model_name: 模型名称
            answer_reserve: 预留的回答空间（token），默认使用default_answer_reserve

        Returns:
            (总上下文窗口, 已使用空间, 预留回答空间, 可用空间, 是否足够)
        """
        context_window = self.get_context_window(model_name)
        reserve = (
            answer_reserve
            if answer_reserve is not None
            else self.default_answer_reserve
        )

        used_space = history_tokens + current_question_tokens
        available_space = context_window - used_space - reserve

        is_sufficient = available_space >= 0

        return (
            context_window,  # 总上下文窗口
            used_space,  # 已使用空间
            reserve,  # 预留回答空间
            available_space,  # 可用空间
            is_sufficient,  # 是否足够
        )

    def format_context_analysis(
        self,
        history_tokens: int,
        current_question_tokens: int,
        model_name: str = "default",
        answer_reserve: Optional[int] = None,
    ) -> str:
        """格式化上下文分析结果

        Args:
            history_tokens: 历史对话的token数
            current_question_tokens: 当前问题的token数
            model_name: 模型名称
            answer_reserve: 预留的回答空间（token）

        Returns:
            格式化的分析结果
        """
        context_window, used_space, reserve, available_space, is_sufficient = (
            self.calculate_available_space(
                history_tokens, current_question_tokens, model_name, answer_reserve
            )
        )

        status = "✅ 空间足够" if is_sufficient else "❌ 空间不足"

        return f"""
                上下文窗口分析：
                ┌───────────────────────┬─────────┐
                │ 项目                 │ Token数 │
                ├───────────────────────┼─────────┤
                │ 总上下文窗口         │ {context_window:>7} │
                │ 历史对话             │ {history_tokens:>7} │
                │ 当前问题             │ {current_question_tokens:>7} │
                │ 已使用空间           │ {used_space:>7} │
                │ 预留回答空间         │ {reserve:>7} │
                │ 可用空间             │ {available_space:>7} │
                └───────────────────────┴─────────┘
                状态：{status}
                """

    def calculate_max_tokens(
        self, input_tokens: int, model_name: str = "default", safety_buffer: int = 200
    ) -> int:
        """计算最大输出token数

        Args:
            input_tokens: 输入的token数（历史数据 + prompt）
            model_name: 模型名称
            safety_buffer: 安全缓冲token数

        Returns:
            最大输出token数
        """
        context_window = self.get_context_window(model_name)
        max_tokens = context_window - input_tokens - safety_buffer
        # 确保max_tokens至少为1
        return max(1, max_tokens)

    def calculate_input_tokens(
        self, prompt: str, history: str = "", model_name: str = "default"
    ) -> int:
        """计算输入的总token数

        Args:
            prompt: 当前prompt
            history: 历史数据
            model_name: 模型名称

        Returns:
            输入的总token数
        """
        prompt_tokens = self.count_tokens(prompt, model_name)
        history_tokens = self.count_tokens(history, model_name)
        return prompt_tokens + history_tokens


# 全局实例
token_counter = TokenCounter()
