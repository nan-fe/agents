import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


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
