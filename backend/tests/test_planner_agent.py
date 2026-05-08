import asyncio
from app.agents.planner_agent import PlannerAgent

async def test_planner_agent():
    """测试策划Agent"""
    print("开始测试策划Agent...")
    agent = PlannerAgent()
    print("创建策划Agent成功")
    
    print("开始运行策划Agent...")
    # 测试带日志回调的情况
    logs = []
    def log_callback(agent_name, message):
        logs.append(f"{agent_name}: {message}")
    
    result = await agent.run("给工作党推荐一个按摩器", log_callback)
    print(f"策划Agent运行完成，结果: {result}")
    print(f"Result type: {type(result)}")
    print(f"Logs: {logs}")
    
    # 验证返回结果的字段
    assert result.target_audience is not None
    assert isinstance(result.target_audience, list)
    assert len(result.target_audience) > 0
    assert len(result.core_selling_points) > 0
    assert isinstance(result.core_selling_points, list)
    assert result.tone_style is not None
    assert isinstance(result.tone_style, str)
    assert result.image_requirements is not None
    assert isinstance(result.image_requirements, str)
    assert result.topic is not None
    assert isinstance(result.topic, str)
    
    print("测试策划Agent成功！")

if __name__ == "__main__":
    asyncio.run(test_planner_agent())
    # asyncio.run(test_planner_agent_with_default_values())
