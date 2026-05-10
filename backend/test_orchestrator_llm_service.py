import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.services.orchestrator_llm_service import OrchestratorLLMService
from langchain_core.messages import HumanMessage, SystemMessage


# async def test_analyze_intent():
#     """测试意图分析方法"""
#     print("=" * 60)
#     print("测试 analyze_intent 方法")
#     print("=" * 60)

#     service = OrchestratorLLMService()

#     test_cases = [
#         {
#             "name": "新任务 - 首次输入",
#             "user_input": "推荐一款适合学生的蓝牙耳机",
#             "chat_history": []
#         },
#         {
#             "name": "修改文案 - 补充内容",
#             "user_input": "在之前的基础上，补充更多使用心得",
#             "chat_history": [
#                 HumanMessage(content="推荐一款适合学生的蓝牙耳机"),
#                 SystemMessage(content="已为您生成蓝牙耳机推荐文案...")
#             ]
#         },
#         {
#             "name": "修改图片 - 重新生成图",
#             "user_input": "换一个更清新的背景图",
#             "chat_history": [
#                 HumanMessage(content="推荐一款适合学生的蓝牙耳机"),
#                 SystemMessage(content="已为您生成文案和配图")
#             ]
#         },
#         {
#             "name": "更改主题 - 改题",
#             "user_input": "不要蓝牙耳机了，改成推荐充电宝",
#             "chat_history": [
#                 HumanMessage(content="推荐一款适合学生的蓝牙耳机"),
#                 SystemMessage(content="已为您生成蓝牙耳机推荐文案...")
#             ]
#         },
#         {
#             "name": "简单提问 - 非创作任务",
#             "user_input": "今天天气怎么样？",
#             "chat_history": []
#         }
#     ]

#     for i, test_case in enumerate(test_cases, 1):
#         print(f"\n--- 测试 {i}：{test_case['name']} ---")
#         print(f"用户输入: {test_case['user_input']}")

#         result = await service.analyze_intent(
#             test_case['user_input'],
#             test_case['chat_history']
#         )

#         print(f"识别意图: {result}")

#         assert result in ["new_task", "refine_content", "refine_image", "change_topic", "ask_question"], \
#             f"未知意图类型: {result}"

#         print(f"✅ 测试 {i} 通过！")

#     return len(test_cases)


async def test_route_task():
    """测试路由决策方法"""
    print("\n" + "=" * 60)
    print("测试 route_task 方法")
    print("=" * 60)

    service = OrchestratorLLMService()

    test_cases = [
        {
            "name": "新建任务 - 完整流程",
            "user_input": "推荐一款适合学生的蓝牙耳机",
            "planning_result": {
                "topic": "学生蓝牙耳机推荐",
                "target_audience": ["学生", "年轻人"],
                "core_selling_points": ["性价比", "续航", "颜值"],
                "tone_style": "活泼有趣",
                "image_requirements": "清新校园风格"
            },
            "intent": "new_task",
            "expected_agents": ["RagAgent", "CopywriterAgent", "ImageAgent", "ReviewerAgent"]
        },
        {
            "name": "修改文案 - 只需文案Agent",
            "user_input": "把语气改得更专业一些",
            "planning_result": {
                "topic": "学生蓝牙耳机推荐",
                "target_audience": ["学生", "年轻人"],
                "core_selling_points": ["性价比", "续航", "颜值"],
                "tone_style": "活泼有趣",
                "image_requirements": "清新校园风格"
            },
            "intent": "refine_content",
            "expected_agents": ["CopywriterAgent", "ReviewerAgent"]
        },
        {
            "name": "修改图片 - 只需图片Agent",
            "user_input": "换一个更清新的背景图",
            "planning_result": {
                "topic": "学生蓝牙耳机推荐",
                "target_audience": ["学生", "年轻人"],
                "core_selling_points": ["性价比", "续航", "颜值"],
                "tone_style": "活泼有趣",
                "image_requirements": "清新校园风格"
            },
            "intent": "refine_image",
            "expected_agents": ["ImageAgent", "ReviewerAgent"]
        },
        {
            "name": "更改主题 - 完整流程",
            "user_input": "不要蓝牙耳机了，改成推荐充电宝",
            "planning_result": {
                "topic": "学生蓝牙耳机推荐",
                "target_audience": ["学生", "年轻人"],
                "core_selling_points": ["性价比", "续航", "颜值"],
                "tone_style": "活泼有趣",
                "image_requirements": "清新校园风格"
            },
            "intent": "change_topic",
            "expected_agents": ["RagAgent", "CopywriterAgent", "ImageAgent", "ReviewerAgent"]
        },
        {
            "name": "简单任务 - 跳过部分Agent",
            "user_input": "写一段简单的防晒霜文案",
            "planning_result": {
                "topic": "防晒霜推荐",
                "target_audience": ["女性", "上班族"],
                "core_selling_points": ["防晒", "保湿"],
                "tone_style": "温馨实用",
                "image_requirements": ""
            },
            "intent": "new_task",
            "expected_agents": ["CopywriterAgent", "ReviewerAgent"]
        },
        {
            "name": "复杂任务 - 多Agent协作",
            "user_input": "为新款手机制作完整的营销方案",
            "planning_result": {
                "topic": "新款手机营销",
                "target_audience": ["科技爱好者", "商务人士"],
                "core_selling_points": ["性能", "拍照", "续航"],
                "tone_style": "专业科技",
                "image_requirements": "高端科技感"
            },
            "intent": "new_task",
            "expected_agents": ["RagAgent", "CopywriterAgent", "ImageAgent", "ReviewerAgent"]
        }
    ]

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n--- 测试 {i}：{test_case['name']} ---")
        print(f"用户输入: {test_case['user_input']}")
        print(f"意图类型: {test_case['intent']}")

        result = await service.route_task(
            test_case['user_input'],
            test_case['planning_result'],
            test_case['intent']
        )

        print(f"路由决策:")
        print(f"  任务类型: {result.task_type}")
        print(f"  调用Agent: {result.agents_to_call}")
        print(f"  优先级: {result.priority_order}")
        print(f"  理由: {result.reasoning}")

        assert hasattr(result, 'task_type'), "缺少 task_type 字段"
        assert hasattr(result, 'agents_to_call'), "缺少 agents_to_call 字段"
        assert hasattr(result, 'reasoning'), "缺少 reasoning 字段"
        assert hasattr(result, 'priority_order'), "缺少 priority_order 字段"
        assert isinstance(result.agents_to_call, list), "agents_to_call 应为列表"
        assert isinstance(result.priority_order, list), "priority_order 应为列表"

        expected_agents = test_case.get('expected_agents', [])
        if expected_agents:
            assert set(result.agents_to_call) == set(expected_agents), \
                f"agents_to_call 不匹配: 期望 {expected_agents}, 实际 {result.agents_to_call}"

        print(f"✅ 测试 {i} 通过！")

    return len(test_cases)


async def test_all():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("开始测试 OrchestratorLLMService")
    print("=" * 60)

    passed = 0
    total = 0

    # try:
    #     total += await test_analyze_intent()
    #     passed += total
    # except Exception as e:
    #     print(f"❌ analyze_intent 测试失败: {str(e)}")

    try:
        total += await test_route_task()
        passed += total
    except Exception as e:
        print(f"❌ route_task 测试失败: {str(e)}")

    # print("\n" + "=" * 60)
    # print(f"测试完成！通过: {passed}/{total}")
    # print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_all())
