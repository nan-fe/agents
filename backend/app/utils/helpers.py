import logging
import asyncio
from typing import Callable, Any

# 配置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


async def retry_async(
    func: Callable, max_retries: int = 3, delay: float = 1.0, **kwargs
) -> Any:
    """异步重试装饰器

    Args:
        func: 异步函数
        max_retries: 最大重试次数
        delay: 重试延迟（秒）
        **kwargs: 函数参数

    Returns:
        函数返回值
    """
    retries = 0
    while retries < max_retries:
        try:
            return await func(**kwargs)
        except Exception as e:
            retries += 1
            logger.warning(f"尝试 {retries}/{max_retries} 失败: {e}")
            if retries < max_retries:
                await asyncio.sleep(delay)
            else:
                raise


def parse_agent_output(output: str, expected_keys: list) -> dict:
    """解析Agent输出

    Args:
        output: Agent输出文本
        expected_keys: 期望的键列表

    Returns:
        解析后的字典
    """
    result = {}
    for key in expected_keys:
        # 简单的解析逻辑，实际项目中可能需要更复杂的处理
        if f"{key}:" in output:
            start_idx = output.find(f"{key}:") + len(f"{key}:")
            end_idx = (
                output.find("\n", start_idx)
                if "\n" in output[start_idx:]
                else len(output)
            )
            result[key] = output[start_idx:end_idx].strip()
    return result
