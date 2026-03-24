from app.services.planning_chain import PlanningChain
import asyncio

async def test_planning_chain():
    print("开始测试 PlanningChain...")
    chain = PlanningChain()
    print("创建 PlanningChain 成功")
    
    result = await chain.run("推荐一款适合学生党的平价防晒霜，清爽不油腻")
    print("测试结果:", result)
    print("测试完成")

if __name__ == "__main__":
    asyncio.run(test_planning_chain())
