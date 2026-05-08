import asyncio
from app.agents.copywriter_agent import CopywriterAgent

async def testCopyWriter():
    # 创建 CopywriterAgent 实例
    copywriter_agent = CopywriterAgent()
    print("创建 CopywriterAgent 成功")

    # 定义日志回调函数
    async def log_callback(agent, message):
        print(f"[{agent}] {message}")

    # 测试 1：生成防晒霜文案
    print("\n=== 测试 1：生成防晒霜文案 ===")
    test_data1 = {
        'topic': '防晒霜',
        'target_audience': ['通勤打工人'],
        'core_selling_points': ['SPF 30+ 高效防护', '轻薄透气 不闷痘', '多功能防护 修护皮肤'],
        'tone_style': '亲切自然',
        'user_input': '推荐一下防晒霜给通勤的打工人'
    }
    result1 = await copywriter_agent.run(test_data1, log_callback)
    print(f"测试 1 结果: {result1}")

    # 测试 2：补充品牌名字和购买渠道
    print("\n=== 测试 2：补充品牌名字和购买渠道 ===")
    test_data2 = {
        'topic': '防晒霜',
        'target_audience': ['通勤打工人'],
        'core_selling_points': ['SPF 30+ 高效防护', '轻薄透气 不闷痘', '多功能防护 修护皮肤'],
        'tone_style': '亲切自然',
        'user_input': '我觉得文案内容可以补充点品牌名字，以及购买渠道，hashtag 也可以加上品牌名字'
    }
    # 传递历史数据
    history_data = f"上次生成的文案信息：\n标题：{result1.title}\n内容：{result1.content}\n标签：{', '.join(result1.hashtags)}"
    result2 = await copywriter_agent.run(test_data2, log_callback, history=history_data)
    print(f"测试 2 结果: {result2}")

    # 测试 3：增加使用步骤和注意事项
    print("\n=== 测试 3：增加使用步骤和注意事项 ===")
    test_data3 = {
        'topic': '防晒霜',
        'target_audience': ['通勤打工人'],
        'core_selling_points': ['SPF 30+ 高效防护', '轻薄透气 不闷痘', '多功能防护 修护皮肤'],
        'tone_style': '亲切自然',
        'user_input': '文案内容在这个基础上增加使用的步骤和注意事项'
    }
    # 传递历史数据
    history_data = f"上次生成的文案信息：\n标题：{result2.title}\n内容：{result2.content}\n标签：{', '.join(result2.hashtags)}"
    result3 = await copywriter_agent.run(test_data3, log_callback, history=history_data)
    print(f"测试 3 结果: {result3}")

if __name__ == "__main__":
    asyncio.run(testCopyWriter())