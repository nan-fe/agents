import asyncio

from app.agents.reviewer_agent import ReviewerAgent


async def testReviewerAgent():
    reviewer_agent = ReviewerAgent()
    print("创建 ReviewerAgent 成功")

    async def log_callback(agent, message):
        print(f"[{agent}] {message}")

    test_cases = [
        {
            "name": "正常内容 - 通过审核",
            "input_data": {
                "copywriting_title": "🔥夏日必备！这款防晒霜真的绝了！",
                "copywriting_content": "姐妹们！今天给大家安利一款我无限回购的防晒霜！SPF50+ PA++++，质地轻薄不闷痘，成膜快不搓泥！夏天必备！",
                "copywriting_hashtags": ["#防晒霜推荐", "#夏日必备", "#护肤分享"],
                "image_url": "https://example.com/sunscreen.jpg",
                "image_prompt": "一瓶防晒霜放在白色背景上，产品清晰可见",
            },
            "expected_approved": True,
        },
        {
            "name": "内容含夸大宣传 - 需要修改",
            "input_data": {
                "copywriting_title": "包治百病！这款神药太神奇了！",
                "copywriting_content": "这款药可以治疗所有疾病，吃了马上见效，无效退款！",
                "copywriting_hashtags": ["#神药", "#包治百病", "#特效药"],
                "image_url": "https://example.com/medicine.jpg",
                "image_prompt": "一盒药放在桌子上",
            },
            "expected_approved": False,
        },
        {
            "name": "敏感内容 - 拒绝通过",
            "input_data": {
                "copywriting_title": "如何快速减肥？三天瘦十斤秘籍！",
                "copywriting_content": "吃这款减肥药，三天瘦十斤不是梦！完全不需要运动和节食！",
                "copywriting_hashtags": ["#快速减肥", "#减肥药", "#三天瘦十斤"],
                "image_url": "https://example.com/diet.jpg",
                "image_prompt": "减肥药产品图",
            },
            "expected_approved": False,
        },
        {
            "name": "内容适合目标人群 - 通过审核",
            "input_data": {
                "copywriting_title": "宝妈必看！宝宝用品推荐清单",
                "copywriting_content": "作为一个两岁宝宝的妈妈，今天给大家分享一些我觉得超级实用的宝宝用品！都是亲测好用的！",
                "copywriting_hashtags": ["#宝妈分享", "#宝宝用品", "#育儿好物"],
                "image_url": "https://example.com/baby.jpg",
                "image_prompt": "温馨的母婴用品场景",
            },
            "expected_approved": True,
        },
        {
            "name": "内容不适合目标人群 - 需要修改",
            "input_data": {
                "copywriting_title": "给宝宝推荐这些保健品",
                "copywriting_content": "宝宝从出生就要开始吃各种保健品，DHA、鱼肝油、钙片一个都不能少！",
                "copywriting_hashtags": ["#宝宝保健品", "#育儿推荐", "#婴儿营养"],
                "image_url": "https://example.com/supplements.jpg",
                "image_prompt": "各种宝宝保健品",
            },
            "expected_approved": False,
        },
        {
            "name": "图片描述不当 - 需要调整",
            "input_data": {
                "copywriting_title": "这款衣服太美了！",
                "copywriting_content": "姐妹们！这件衣服真的绝绝子！穿上秒变仙女！",
                "copywriting_hashtags": ["#穿搭分享", "#仙女裙", "#购物分享"],
                "image_url": "https://example.com/clothes.jpg",
                "image_prompt": "一个穿着暴露的模特",
            },
            "expected_approved": False,
        },
        {
            "name": "标签不当 - 需要修改",
            "input_data": {
                "copywriting_title": "今天心情不错",
                "copywriting_content": "今天天气很好，心情也不错，出来散散步~",
                "copywriting_hashtags": ["#政治敏感话题", "#违法内容", "#不良信息"],
                "image_url": "https://example.com/walk.jpg",
                "image_prompt": "一个人在公园散步",
            },
            "expected_approved": False,
        },
        {
            "name": "内容涉及违规营销 - 拒绝通过",
            "input_data": {
                "copywriting_title": "内部渠道！大牌护肤品五折代购！",
                "copywriting_content": "我有内部渠道，可以拿到专柜五折的护肤品！绝对正品！加我微信xxx",
                "copywriting_hashtags": ["#代购", "#内部渠道", "#正品保证"],
                "image_url": "https://example.com/cosmetics.jpg",
                "image_prompt": "各种大牌护肤品",
            },
            "expected_approved": False,
        },
        {
            "name": "优质内容 - 通过审核",
            "input_data": {
                "copywriting_title": "✨新手化妆教程｜日常通勤妆超详细步骤",
                "copywriting_content": "姐妹们！今天出一个超详细的新手化妆教程！从护肤到底妆到眼妆，一步一步教你画一个美美的通勤妆！",
                "copywriting_hashtags": ["#化妆教程", "#新手化妆", "#通勤妆容"],
                "image_url": "https://example.com/makeup.jpg",
                "image_prompt": "化妆步骤示意图，清新自然风格",
            },
            "expected_approved": True,
        },
    ]

    passed_count = 0
    failed_count = 0

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n=== 测试 {i}：{test_case['name']} ===")
        print(f"标题: {test_case['input_data']['copywriting_title']}")

        result = await reviewer_agent.run(test_case["input_data"], log_callback)

        print("审核结果:")
        print(f"  通过: {result.approved}")
        print(f"  反馈: {result.feedback}")
        print(f"  修改建议: {result.corrections}")

        assert hasattr(result, "approved"), "缺少 approved 字段"
        assert hasattr(result, "feedback"), "缺少 feedback 字段"

        if result.approved == test_case["expected_approved"]:
            print(f"✅ 测试 {i} 通过！")
            passed_count += 1
        else:
            print(
                f"❌ 测试 {i} 失败！预期: {test_case['expected_approved']}, 实际: {result.approved}"
            )
            failed_count += 1
            assert hasattr(result, "corrections"), "缺少 corrections 字段"

    print(f"\n{'=' * 60}")
    print(f"测试完成！通过: {passed_count}, 失败: {failed_count}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    asyncio.run(testReviewerAgent())
