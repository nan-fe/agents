import asyncio
from app.agents.planner_agent import PlannerAgent

async def test_planner_agent():
    """测试策划Agent"""
    print("开始测试策划Agent...")
    agent = PlannerAgent()
    
    print("开始运行策划Agent...")
    # 测试带日志回调的情况
    logs = []
    def log_callback(agent_name, message):
        logs.append(f"{agent_name}: {message}")
    

    test_cases = [
        {
            "name": "护肤品 - 敏感肌人群 - 温和专业风格",
            "input_data": "推荐适合敏感肌的护肤品，成分要温和，不刺激，最好是医美级别的",
            "expected_category": "护肤品"
        },
        {
            "name": "电子产品 - 学生党人群 - 活泼有趣风格",
            "input_data": "推荐适合大学生的平价蓝牙耳机，颜值高，续航久，性价比高",
            "expected_category": "电子产品"
        },
        {
            "name": "服装 - 职场新人人群 - 优雅通勤风格",
            "input_data": "推荐适合刚入职女生的通勤穿搭，简约大方，显气质，价格适中",
            "expected_category": "服装"
        },
        {
            "name": "家居用品 - 宝妈人群 - 温馨实用风格",
            "input_data": "推荐适合有宝宝家庭的收纳神器，安全环保，节省空间，方便打理",
            "expected_category": "家居用品"
        },
        {
            "name": "美食零食 - 办公室人群 - 轻松治愈风格",
            "input_data": "推荐适合办公室的健康零食，低卡低糖，方便分享，颜值高",
            "expected_category": "美食零食"
        },
        {
            "name": "运动装备 - 健身达人人群 - 专业活力风格",
            "input_data": "推荐适合健身房使用的运动装备，舒适透气，时尚好看，功能性强",
            "expected_category": "运动装备"
        },
        {
            "name": "美妆彩妆 - 新手小白人群 - 甜美可爱风格",
            "input_data": "推荐适合化妆新手的入门彩妆套装，颜色日常，容易上手，性价比高",
            "expected_category": "美妆彩妆"
        },
        {
            "name": "宠物用品 - 铲屎官人群 - 萌宠治愈风格",
            "input_data": "推荐适合猫咪的高颜值用品，实用又好看，提升猫咪幸福感",
            "expected_category": "宠物用品"
        },
        {
            "name": "文具手账 - 学生人群 - 清新文艺风格",
            "input_data": "推荐适合学生的手账素材和文具，颜值高，好用不贵，激发创作灵感",
            "expected_category": "文具手账"
        },
        {
            "name": "母婴用品 - 孕期妈妈人群 - 温柔安心风格",
            "input_data": "推荐适合孕期妈妈的必备好物，安全舒适，提升孕期幸福感",
            "expected_category": "母婴用品"
        }
    ]

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n=== 测试 {i}：{test_case['name']} ===")
        print(f"输入: {test_case['input_data']}")
        
        result = await agent.run(test_case['input_data'], log_callback)
        
        print(f"输出结果:")
        print(f"  主题: {result.topic}")
        print(f"  目标人群: {result.target_audience}")
        print(f"  核心卖点: {result.core_selling_points}")
        print(f"  语气风格: {result.tone_style}")
        print(f"  图片需求: {result.image_requirements}")
        print(f"  商品类别: {result.product_category}")
        
        assert hasattr(result, 'topic'), "缺少 topic 字段"
        assert hasattr(result, 'target_audience'), "缺少 target_audience 字段"
        assert hasattr(result, 'core_selling_points'), "缺少 core_selling_points 字段"
        assert hasattr(result, 'tone_style'), "缺少 tone_style 字段"
        assert hasattr(result, 'image_requirements'), "缺少 image_requirements 字段"
        assert hasattr(result, 'product_category'), "缺少 product_category 字段"
        
        print(f"✅ 测试 {i} 通过！")

if __name__ == "__main__":
    asyncio.run(test_planner_agent())
