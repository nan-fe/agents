import asyncio
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

import pytest

from app.agents.image_agent import ImageAgent
from app.models.schemas import ImageAgentInput


@pytest.mark.network
async def test_image_agent():
    print("开始测试图片Agent...")
    agent = ImageAgent()
    print("创建图片Agent成功")

    agent = ImageAgent()
    logs = []

    def log_callback(agent_name, message):
        logs.append(f"{agent_name}: {message}")

    # planning_result = ImageAgentInput(
    #     **{
    #         "product_category": "防晒霜",
    #         "image_requirements": "阳光下的使用场景，防晒后的状态",
    #         "copywriting_content": "姐妹们！挖到宝了！💥这个【小蓝瓶防晒】简直是为学生党量身定做！💰50r/30ml的性价比太绝了！SPF50+ PA++++防晒力吊打其他国货💪\n\n🌞实测效果：上周去迪士尼暴走8小时，防晒霜都没补涂！脸蛋一点没晒红，闺蜜都问我是不是偷偷打了光！📸\n\n✨使用体验：质地是冰激凌慕斯质地！一抹化水超好推开，成膜超快！上课前随手抹两下，完全不影响戴口罩😷和戴眼镜！学生党早八赶地铁真的超方便～\n\n🛒重点来了！现在买还送同款小样+防晒冰袖！宿舍姐妹拼团更划算！这波不亏！💸\n\n学生党们快冲！这个夏天一起做不晒黑的小仙女！👑💖",
    #         "topic": "防晒护肤",
    #         "target_audience": ["学生党"],
    #         "core_selling_points": ["平价", "防晒指数高", "使用方便"],
    #         "tone_style": "亲切自然",
    #         "user_input": "推荐一下防晒霜",
    #         "chat_history": "",
    #     }
    # )
    # result = await agent.run(planning_result, log_callback)
    # print(f"策划Agent运行完成，结果: {result}")
    # # 传递历史数据
    # history_data = f"上次图片的文案信息：{result.prompt}"
    # planning_result2 = ImageAgentInput(
    #     **{
    #         "product_category": "防晒霜",
    #         "image_requirements": "阳光下的使用场景，防晒后的状态",
    #         "copywriting_content": "姐妹们！挖到宝了！💥这个【小蓝瓶防晒】简直是为学生党量身定做！💰50r/30ml的性价比太绝了！SPF50+ PA++++防晒力吊打其他国货💪\n\n🌞实测效果：上周去迪士尼暴走8小时，防晒霜都没补涂！脸蛋一点没晒红，闺蜜都问我是不是偷偷打了光！📸\n\n✨使用体验：质地是冰激凌慕斯质地！一抹化水超好推开，成膜超快！上课前随手抹两下，完全不影响戴口罩😷和戴眼镜！学生党早八赶地铁真的超方便～\n\n🛒重点来了！现在买还送同款小样+防晒冰袖！宿舍姐妹拼团更划算！这波不亏！💸\n\n学生党们快冲！这个夏天一起做不晒黑的小仙女！👑💖",
    #         "topic": "防晒护肤",
    #         "target_audience": ["学生党"],
    #         "core_selling_points": ["平价", "防晒指数高", "使用方便"],
    #         "tone_style": "亲切自然",
    #         "user_input": "场景可以在登山的时候，体现防晒霜的使用",
    #         "chat_history": history_data,
    #     }
    # )

    # result2 = await agent.run(planning_result2, log_callback)
    # print(f"策划Agent运行完成 result2，结果: {result2}")

    # history_data2 = f"上次图片的文案信息：{result2.prompt}"
    planning_result3 = ImageAgentInput(
        **{
            "product_category": "UNIKKO游霓可装饰陶瓷马克杯",
            "image_requirements": "桌面静物产品摄影，突出杯身花纹和容量信息，商品本体清晰可见",
            "copywriting_content": (
                "款名：UNIKKO游霓可装饰陶瓷马克杯；容量：400毫升；材质：白色陶瓷；"
                "颜色：白色+深酒红色+粉色+泥土色；产地：泰国白陶材质。"
                "采用白陶材质，可冰箱存放，可微波炉和烤箱加热，洗碗机清洗无负担。"
            ),
            "topic": "家居杯具",
            "target_audience": ["家居生活爱好者", "办公人群"],
            "core_selling_points": [
                "400毫升大容量",
                "白陶材质耐用",
                "可冰箱/微波炉/烤箱/洗碗机使用",
            ],
            "tone_style": "温暖自然",
            "user_input": "生成一张突出马克杯本体和配色细节的产品图",
            # "chat_history": history_data2,
        }
    )
    result3 = await agent.run(planning_result3, log_callback)
    print(f"策划Agent运行完成 result3，结果: {result3}")


if __name__ == "__main__":
    asyncio.run(test_image_agent())
