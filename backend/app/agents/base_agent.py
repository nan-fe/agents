from abc import ABC, abstractmethod
from typing import Any

from app.utils.log_callback import emit_log


class BaseAgent(ABC):
    """Agent基类"""

    def __init__(self, name: str, role: str):
        """初始化Agent

        Args:
            name: Agent名称
            role: Agent角色
        """
        self.name = name
        self.role = role

    @abstractmethod
    async def run(self, input_data: Any, log_callback: callable | None = None) -> Any:
        """运行Agent

        Args:
            input_data: 输入数据
            log_callback: 日志回调函数

        Returns:
            输出结果
        """
        pass

    async def log(self, message: str, log_callback: callable | None = None):
        """记录日志

        Args:
            message: 日志消息
            log_callback: 日志回调函数
        """
        if log_callback:
            await emit_log(log_callback, self.name, message)
