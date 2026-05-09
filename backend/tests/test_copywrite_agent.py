import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.agents.copywriter_agent import CopywriterAgent

async def test_copywriter():
    copywriter_agent = CopywriterAgent()
    print("创建 CopywriterAgent 成功")

    async def log_callback(agent, message):
        print(f"[{agent}] {message}")

    test_cases = [
        {
            "name": "护肤品 - 敏感肌人群 - 温和专业风格",
            "input_data": {
                'topic': '敏感肌护肤品',
                'target_audience': ['敏感肌人群', '成分党'],
                'core_selling_points': ['医美级别成分', '温和不刺激', '修护屏障'],
                'tone_style': '温和专业',
                'user_input': '推荐适合敏感肌的护肤品，成分要温和安全'
            },
            "has_history": False
        },
        {
            "name": "电子产品 - 学生党 - 活泼有趣风格",
            "input_data": {
                'topic': '平价蓝牙耳机',
                'target_audience': ['大学生', '学生党'],
                'core_selling_points': ['高颜值', '长续航', '性价比高'],
                'tone_style': '活泼有趣',
                'user_input': '推荐适合学生党的平价蓝牙耳机'
            },
            "has_history": False
        },
        {
            "name": "服装 - 职场新人 - 优雅通勤风格",
            "input_data": {
                'topic': '通勤穿搭',
                'target_audience': ['职场新人', '刚入职女生'],
                'core_selling_points': ['简约大方', '显气质', '价格适中'],
                'tone_style': '优雅通勤',
                'user_input': '推荐适合刚入职女生的通勤穿搭'
            },
            "has_history": False
        },
        {
            "name": "家居用品 - 宝妈人群 - 温馨实用风格",
            "input_data": {
                'topic': '宝宝收纳神器',
                'target_audience': ['宝妈', '有宝宝家庭'],
                'core_selling_points': ['安全环保', '节省空间', '方便打理'],
                'tone_style': '温馨实用',
                'user_input': '推荐适合有宝宝家庭的收纳神器'
            },
            "has_history": False
        },
        {
            "name": "美食零食 - 办公室人群 - 轻松治愈风格",
            "input_data": {
                'topic': '办公室健康零食',
                'target_audience': ['办公室白领', '上班族'],
                'core_selling_points': ['低卡低糖', '方便分享', '颜值高'],
                'tone_style': '轻松治愈',
                'user_input': '推荐适合办公室的健康零食'
            },
            "has_history": False
        },
        {
            "name": "运动装备 - 健身达人 - 专业活力风格",
            "input_data": {
                'topic': '健身房运动装备',
                'target_audience': ['健身达人', '运动爱好者'],
                'core_selling_points': ['舒适透气', '时尚好看', '功能性强'],
                'tone_style': '专业活力',
                'user_input': '推荐适合健身房使用的运动装备'
            },
            "has_history": False
        },
        {
            "name": "美妆彩妆 - 新手小白 - 甜美可爱风格",
            "input_data": {
                'topic': '入门彩妆套装',
                'target_audience': ['化妆新手', '学生'],
                'core_selling_points': ['颜色日常', '容易上手', '性价比高'],
                'tone_style': '甜美可爱',
                'user_input': '推荐适合化妆新手的入门彩妆套装'
            },
            "has_history": False
        },
        {
            "name": "宠物用品 - 铲屎官 - 萌宠治愈风格",
            "input_data": {
                'topic': '猫咪高颜值用品',
                'target_audience': ['铲屎官', '猫咪爱好者'],
                'core_selling_points': ['实用又好看', '提升猫咪幸福感', '安全材质'],
                'tone_style': '萌宠治愈',
                'user_input': '推荐适合猫咪的高颜值用品'
            },
            "has_history": False
        },
        {
            "name": "文具手账 - 学生 - 清新文艺风格",
            "input_data": {
                'topic': '手账素材文具',
                'target_audience': ['学生', '手账爱好者'],
                'core_selling_points': ['颜值高', '好用不贵', '激发创作灵感'],
                'tone_style': '清新文艺',
                'user_input': '推荐适合学生的手账素材和文具'
            },
            "has_history": False
        },
        {
            "name": "母婴用品 - 孕期妈妈 - 历史数据场景",
            "input_data": {
                'topic': '孕期必备好物',
                'target_audience': ['孕期妈妈', '准妈妈'],
                'core_selling_points': ['安全舒适', '提升孕期幸福感', '实用性强'],
                'tone_style': '温柔安心',
                'user_input': '在之前的基础上，补充更多孕期注意事项和使用心得'
            },
            "has_history": True,
            "history_topic": "孕期护肤",
            "history_content": "孕期妈妈一定要注意护肤！选择温和无刺激的产品很重要，推荐使用含有天然植物成分的护肤品，既能保湿又安全。记得做好防晒，孕期皮肤更敏感哦~",
            "history_hashtags": ["#孕期护肤", "#准妈妈必备", "#安全护肤"]
        }
    ]

    results = []
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n=== 测试 {i}：{test_case['name']} ===")
        print(f"输入: {test_case['input_data']['user_input']}")
        
        history_data = ""
        if test_case.get("has_history"):
            history_data = f"上次生成的文案信息：\n标题：{test_case.get('history_topic', '')}\n内容：{test_case.get('history_content', '')}\n标签：{', '.join(test_case.get('history_hashtags', []))}"
            print(f"历史数据: 已提供")
        
        result = await copywriter_agent.run(test_case['input_data'], log_callback, history=history_data)
        results.append(result)
        
        print(f"输出结果:")
        print(f"  标题: {result.title}")
        print(f"  内容: {result.content[:100]}..." if len(result.content) > 100 else f"  内容: {result.content}")
        print(f"  标签: {result.hashtags}")
        
        assert hasattr(result, 'title'), "缺少 title 字段"
        assert hasattr(result, 'content'), "缺少 content 字段"
        assert hasattr(result, 'hashtags'), "缺少 hashtags 字段"
        assert len(result.title) > 0, "标题不能为空"
        assert len(result.content) > 50, "内容过短"
        assert len(result.hashtags) >= 3, "标签数量不足3个"
        
        print(f"✅ 测试 {i} 通过！")

if __name__ == "__main__":
    asyncio.run(testCopyWriter())