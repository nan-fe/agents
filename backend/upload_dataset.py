import os
from langsmith import Client
from dotenv import load_dotenv

load_dotenv()
# 配置LangSmith
# os.environ["LANGCHAIN_API_KEY"] = "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"

# 初始化LangSmith客户端
client = Client()

# 准备黄金测试集
test_cases = [
    {
        "name": "护肤品推荐",
        "input": {
            "target_audience": ["25-35岁女性", "敏感肌人群"],
            "core_selling_points": ["温和不刺激", "深层补水", "提亮肤色"],
            "tone_style": "亲切自然",
            "topic": "春季护肤必备",
            "user_input": "推荐适合敏感肌的春季护肤品"
        },
        "expected": {
            "title": "敏感肌春季护肤必看！温和补水不踩雷",
            "content": "春季皮肤容易敏感泛红？这款温和不刺激的护肤品必须安排上！\n\n🧴 深层补水，让肌肤喝饱水\n🌸 提亮肤色，焕发春日光彩\n✨ 敏感肌也能放心使用\n\n质地清爽不黏腻，吸收超快，坚持使用皮肤状态真的会变稳定～",
            "hashtags": ["#敏感肌护肤", "#春季护肤", "#补水保湿", "#护肤推荐", "#小红书爆款"]
        }
    },
    {
        "name": "健身器材推广",
        "input": {
            "target_audience": ["健身爱好者", "居家锻炼人群"],
            "core_selling_points": ["方便收纳", "多功能", "静音设计"],
            "tone_style": "活力积极",
            "topic": "居家健身神器",
            "user_input": "推荐适合居家使用的健身器材"
        },
        "expected": {
            "title": "居家健身必备！这款器材让你事半功倍",
            "content": "在家也能高效锻炼！这款健身器材真的太香了～\n\n💪 多功能设计，满足全身训练需求\n🔇 静音设计，不打扰邻居\n📦 方便收纳，不占空间\n\n每天15分钟，轻松get好身材，再也不用去健身房人挤人啦！",
            "hashtags": ["#居家健身", "#健身器材", "#健身打卡", "#懒人健身", "#小红书健身"]
        }
    },
    {
        "name": "咖啡推荐",
        "input": {
            "target_audience": ["咖啡爱好者", "上班族"],
            "core_selling_points": ["醇厚口感", "提神醒脑", "方便快捷"],
            "tone_style": "专业文艺",
            "topic": "办公室必备咖啡",
            "user_input": "推荐适合办公室的咖啡"
        },
        "expected": {
            "title": "办公室咖啡指南｜打工人的提神利器",
            "content": "打工人的早晨，怎么能少了一杯好咖啡？\n\n☕ 醇厚口感，唤醒沉睡的味蕾\n⚡ 提神醒脑，效率up up\n🚀 方便快捷，5分钟搞定\n\n这款咖啡真的是办公室必备，同事喝了都问链接！",
            "hashtags": ["#咖啡推荐", "#办公室必备", "#提神醒脑", "#打工人日常", "#小红书咖啡"]
        }
    },
    {
        "name": "旅行攻略",
        "input": {
            "target_audience": ["年轻旅行者", "预算有限人群"],
            "core_selling_points": ["性价比高", "小众景点", "自由行"],
            "tone_style": "活泼有趣",
            "topic": "周末短途旅行",
            "user_input": "推荐周末短途旅行目的地"
        },
        "expected": {
            "title": "周末短途旅行推荐｜性价比超高的小众目的地",
            "content": "周末想出门浪？这些小众景点太适合了！\n\n💰 性价比高，学生党也能负担\n🌟 小众景点，人少景美\n🧳 自由行攻略，说走就走\n\n不用请长假，周末就能收获一场完美的旅行体验～",
            "hashtags": ["#周末旅行", "#小众景点", "#自由行", "#旅行攻略", "#小红书旅行"]
        }
    },
    {
        "name": "电子产品评测",
        "input": {
            "target_audience": ["数码爱好者", "学生群体"],
            "core_selling_points": ["高性价比", "续航能力强", "轻薄便携"],
            "tone_style": "专业客观",
            "topic": "学生党必备数码产品",
            "user_input": "推荐适合学生党的电子产品"
        },
        "expected": {
            "title": "学生党数码好物｜高性价比不踩雷",
            "content": "学生党看过来！这些数码产品真的能提升学习效率～\n\n💻 轻薄便携，上课图书馆都方便\n🔋 续航能力强，一天不用充电\n💯 高性价比，预算有限也能入手\n\n实测好用，身边同学都被种草了！",
            "hashtags": ["#数码推荐", "#学生党必备", "#高性价比", "#电子产品", "#小红书数码"]
        }
    }
]

# 获取或创建数据集
dataset_name = "Copywriter Agent Test Set"
try:
    # 尝试获取已存在的数据集
    datasets = client.list_datasets()
    dataset = None
    for d in datasets:
        if d.name == dataset_name:
            dataset = d
            break
    
    if not dataset:
        # 创建新数据集
        dataset = client.create_dataset(
            dataset_name=dataset_name,
            description="文案Agent的黄金测试集，包含5个代表性案例"
        )
        print(f"数据集 {dataset_name} 创建成功！")
    else:
        print(f"使用已存在的数据集 {dataset_name}")
    
    # 上传测试案例
    for test_case in test_cases:
        client.create_example(
            inputs=test_case["input"],
            outputs=test_case["expected"],
            dataset_id=dataset.id
        )
    
    print(f"数据集ID: {dataset.id}")
    print(f"共上传了 {len(test_cases)} 个测试案例")
except Exception as e:
    print(f"上传数据集时出错: {e}")
