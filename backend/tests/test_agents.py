# import pytest
# from app.agents.planner_agent import PlannerAgent
# # from app.agents.copywriter_agent import CopywriterAgent
# # from app.agents.image_agent import ImageAgent
# # from app.agents.reviewer_agent import ReviewerAgent
# # from app.agents.orchestrator import AgentOrchestrator

# @pytest.mark.asyncio
# async def test_planner_agent():
#     """测试策划Agent"""
#     print("开始测试策划Agent...")
#     agent = PlannerAgent()
#     print("创建策划Agent成功")
    
#     print("开始运行策划Agent...")
#     # 测试带日志回调的情况
#     logs = []
#     def log_callback(agent_name, message):
#         logs.append(f"{agent_name}: {message}")
    
#     result = await agent.run("给工作党推荐一个按摩器", log_callback)
#     print(f"策划Agent运行完成，结果: {result}")
#     print(f"Result type: {type(result)}")
#     print(f"Logs: {logs}")
    
#     # 验证返回结果的字段
#     assert result.target_audience is not None
#     assert isinstance(result.target_audience, list)
#     assert len(result.target_audience) > 0
#     assert len(result.core_selling_points) > 0
#     assert isinstance(result.core_selling_points, list)
#     assert result.tone_style is not None
#     assert isinstance(result.tone_style, str)
#     assert result.image_requirements is not None
#     assert isinstance(result.image_requirements, str)
#     assert result.topic is not None
#     assert isinstance(result.topic, str)
    
#     print("测试策划Agent成功！")


# @pytest.mark.asyncio
# async def test_planner_agent_with_default_values():
#     """测试策划Agent在异常情况下返回默认值"""
#     print("开始测试策划Agent异常情况...")
#     agent = PlannerAgent()
    
#     # 模拟异常情况（通过修改 PlanningChain 导致异常）
#     original_run = agent.planning_chain.run
    
#     # 临时替换 run 方法，使其抛出异常
#     async def mock_run(input_data):
#         raise Exception("模拟异常")
    
#     agent.planning_chain.run = mock_run
    
#     try:
#         result = await agent.run("给工作党推荐一个按摩器")
#         print(f"策划Agent异常情况结果: {result}")
        
#         # 验证默认值
#         assert result.target_audience == ["通用人群"]
#         assert result.core_selling_points == ["质量好", "价格实惠", "使用方便"]
#         assert result.tone_style == "亲切自然"
#         assert result.image_requirements == "产品实物图，清晰明亮"
#         assert result.topic == "通用产品推荐"
        
#         print("测试策划Agent异常情况成功！")
#     finally:
#         # 恢复原始的 run 方法
#         agent.planning_chain.run = original_run



# # @pytest.mark.asyncio
# # async def test_copywriter_agent():
# #     """测试文案Agent"""
# #     from app.models.schemas import PlanningResult
# #     agent = CopywriterAgent()
# #     planning_result = PlanningResult(
# #         target_audience="学生党",
# #         core_selling_points=["平价", "清爽", "不油腻"],
# #         tone_style="亲切自然",
# #         image_requirements="防晒霜产品图，清爽风格"
# #     )
# #     result = await agent.run(planning_result)
# #     print(f"Result type: {type(result)}")
# #     print('copy writer result',result)
# #     assert result.title is not None
# #     assert result.content is not None
# #     assert len(result.hashtags) > 0


# # @pytest.mark.asyncio
# # async def test_image_agent():
# #     """测试图片Agent"""
# #     from app.models.schemas import PlanningResult
# #     agent = ImageAgent()
# #     planning_result = PlanningResult(
# #         target_audience=["年轻aged"],
# #         core_selling_points=['轻便设计，随身携带的完美选择', '高性价比，品质与实惠并存', '时尚设计，让你轻松展现个性'],
# #         tone_style="亲切自然，充满活力",
# #         image_requirements="简约自然风，场景包括日常使用、户外活动、搭配时尚单品，风格以自然元素为主，突出文火 vibe Pro的轻便与时尚",
# #         product_category="按摩器"
# #     )
# #     result = await agent.run(planning_result)
# #     print('image result',result)
# #     assert result.image_url is not None
# #     assert result.prompt is not None


# # @pytest.mark.asyncio
# # async def test_reviewer_agent():
# #     """测试质检Agent"""
# #     from app.models.schemas import CopywritingResult, ImageResult
# #     agent = ReviewerAgent()
# #     test_data = {
# #         "copywriting": CopywritingResult(
# #             title="平价好物推荐！每天好心情从这里开始！",
# #             content="姐妹们，这个平价好物真的太值得推荐了！物美价廉，用着超方便！\n\n从早到晚都用得上，真的超级喜欢！\n\n#平价好物推荐 #生活小妙招 #每天好心情 #小确幸""姐妹们，这个平价好物真的太值得推荐了！物美价廉，用着超方便！\n\n从早到晚都用得上，真的超级喜欢！\n\n#平价好物推荐 #生活小妙招 #每天好心情 #小确幸",
# #             hashtags=["平价好物推荐", "生活小妙招", "每天好心情", "小确幸"]
# #         ),
# #         "image": ImageResult(
# #             image_url="https://s3.siliconflow.cn/default/outputs/2iezcwurax3jr_224a5d1ea8c4ba4eab67ced5ca867cce_fb201d73_32ea4671_00001_.png?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=AKIAXXXXFILESEXAMPLE%2F20260324%2Fcn-shanghai-1%2Fs3%2Faws4_request&X-Amz-Date=20260324T072419Z&X-Amz-Expires=3600&X-Amz-SignedHeaders=host&X-Amz-Security-Token=eyJhbGciOiJSUzI1NiIsImtpZCI6ImdyYXkiLCJ0eXAiOiJKV1QifQ.eyJzdWIiOiJmYWFzOmRlcDpvcHI6ZDI5Y3UzZ2gzdnZjNzNjNWJpNWc6MGU0OTYiLCJpc3MiOiJodHRwczovL2lhbS5zaWxpY29uZmxvdy5jbiIsImlhdCI6MTc3NDMyNTUxMywiZXhwIjoxNzc0NDk4MzEzLCJ0eXAiOiJzZXJ2aWNlIiwiYXBsdCI6InNmOmZhYXM6ZmFicmljIiwidG50IjoiZDI5Y3UzZ2gzdnZjNzNjNWJpNWciLCJpZCI6ImQ3MTB1Mjk3MTluczczZnI0cXFnIiwiYWNjZXNzIjpbeyJ0eXBlIjoiZmFhcyIsInN1YmplY3RJZCI6ImQyOWN1M2doM3Z2YzczYzViaTVnIiwiYWN0aW9ucyI6WyJmYWFzOmludm9jYXRpb246cHVsbGluZyJdfV19.NGUAodaDGc7oc_fslWTuq1ivp4T7MapAC378GGsY_7-YAbKMO7FMZ0Ku9vM8pwRER4hQ65eZymBC5wJGq4g1LfzF7_uHy11jfaGpmy0zQ2WM2GvKDBMGVTBVJVDkSz9wfYzoyWeCeU6wQDSGASMJMihc3tjJS9oxW_78U6Bb2mCKW5OAoaSKCigZVxwtuPGeNhPhRMi_CGJCAEaCms_h1fPi6u-sGe4g0y8Y9mv-ysqaDYJHqaFMG-DfVRES7bnUFEsyWtlWtkuE9p0T03tbfNd4eYA2tyUHNM2aDSlDnI78eYIF75g86nXAqgml2fKP0oWIAUUuM-Art_uKkU0aoiNlN1Hg94Dpbx_W187D8GiYkLI2r2Susp1WAyORhuiiKbGwKjZeVljNNrAweKlp3EVCVWeMzmpPgNrs9HzhvUK8vwzceLYwWhK8b6WjNq-rBWS2C-68NA2r8Q6cGOI8Ke6FUVbkl8dke2RnreDPpuaYMIZ3MAGJCktrAgrbvPcKvHbS6dkeXiTvxXuhCW6yICqUZIlfAxTdXcexA4Jjav2dl2sVzUm5c15IgM7nJCFsAONwdhkDnswx_j3MdWdcNh0JjcM59yJil19XYlhJv8g66eGHayfDHK0dZBelSIsj6LOx5E6Gd3GXWZ5Creq7EPrKSJzJiQVj4KqrTdapr6U&X-Amz-Signature=7ab4270abb94131da17b3e12607a6b46863df9d4308a584709b99d7c839c894e",
# #             prompt="产品实物图，清晰明亮"
# #         )
# #     }
# #     result = await agent.run(test_data)
# #     print(f"质检Agent运行完成，结果: {result}")
# #     assert isinstance(result.approved, bool)


# # @pytest.mark.asyncio
# # async def test_orchestrator():
# #     """测试协调器"""
# #     orchestrator = AgentOrchestrator()
# #     async def mock_log_callback(agent_name, message):
# #         print(f"{agent_name}: {message}")
# #     result = await orchestrator.run("推荐一款适合学生党的平价防晒霜，清爽不油腻", mock_log_callback)
# #     assert result.get("title") is not None
# #     assert result.get("content") is not None
# #     assert result.get("hashtags") is not None
# #     assert result.get("image_url") is not None
