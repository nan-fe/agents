#!/usr/bin/env python3
"""
测试历史消息管理功能
"""
import asyncio
from app.agents.dialog_orchestrator import DialogOrchestratorAgent

async def test_history_management():
    """测试历史消息管理功能"""
    print("开始测试历史消息管理功能...")
    
    # 创建协调器实例
    orchestrator = DialogOrchestratorAgent()
    
    # 测试会话ID
    session_id = "test_session_123"
    
    # 模拟用户输入
    user_input = "帮我写一篇关于防晒霜的小红书文案"
    
    # 定义日志回调函数
    async def log_callback(agent, message):
        print(f"[{agent}] {message}")
    
    # 第一次执行
    print("\n=== 第一次执行 ===")
    result1 = await orchestrator.run(user_input, session_id, log_callback)
    print(f"第一次执行结果: {result1}")
    
    # 第二次执行（应该使用历史消息）
    print("\n=== 第二次执行 ===")
    user_input2 = "帮我修改一下，增加一些防晒小技巧"
    result2 = await orchestrator.run(user_input2, session_id, log_callback)
    print(f"第二次执行结果: {result2}")
    
    # 检查会话历史
    session_history = orchestrator.get_session_history(session_id)
    print(f"\n会话历史消息数量: {len(session_history.messages)}")
    print(f"会话历史输出数量: {len(session_history.outputs)}")
    
    print("\n测试完成！")

if __name__ == "__main__":
    asyncio.run(test_history_management())
