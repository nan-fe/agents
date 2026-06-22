import asyncio

import pytest

from app.agents.orchestrator.planning import ContentStrategistAgent


@pytest.mark.network
async def test_content_strategist_agent():
    """测试内容策划 Agent"""
    print("开始测试 ContentStrategistAgent...")
    agent = ContentStrategistAgent()

    print("开始运行 ContentStrategistAgent...")
    logs = []

    def log_callback(agent_name, message):
        logs.append(f"{agent_name}: {message}")

    test_cases = [
        {
            "name": "护肤品 - 敏感肌人群 - 温和专业风格",
            "input_data": "推荐适合敏感肌的护肤品，成分要温和，不刺激，最好是医美级别的",
            "expected_category": "护肤品",
        },
        {
            "name": "电子产品 - 学生党人群 - 活泼有趣风格",
            "input_data": "推荐适合大学生的平价蓝牙耳机，颜值高，续航久，性价比高",
            "expected_category": "电子产品",
        },
        {
            "name": "服装 - 职场新人人群 - 优雅通勤风格",
            "input_data": "推荐适合刚入职女生的通勤穿搭，简约大方，显气质，价格适中",
            "expected_category": "服装",
        },
    ]

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n--- 测试 {i}：{test_case['name']} ---")
        print(f"输入: {test_case['input_data']}")

        result = await agent.run(test_case["input_data"], log_callback=log_callback, history="")

        print(f"结果: {result}")
        print(f"日志: {logs}")

        assert hasattr(result, "topic"), "缺少 topic 字段"
        assert hasattr(result, "target_audience"), "缺少 target_audience 字段"
        assert hasattr(result, "core_selling_points"), "缺少 core_selling_points 字段"
        assert hasattr(result, "tone_style"), "缺少 tone_style 字段"
        assert hasattr(result, "image_requirements"), "缺少 image_requirements 字段"
        assert hasattr(result, "product_category"), "缺少 product_category 字段"

        print(f"✅ 测试 {i} 通过！")


if __name__ == "__main__":
    asyncio.run(test_content_strategist_agent())
