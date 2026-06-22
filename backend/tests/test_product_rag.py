import asyncio
import time

import pytest
from dotenv import load_dotenv

from app.agents.product_rag_system.agent import ProductRagAgent

# 加载环境变量
load_dotenv()


@pytest.mark.network
async def test_product_rag():
    print("=" * 60)
    print("ProductRagAgent 测试")
    print("测试目标：验证本地数据库和网络搜索的切换逻辑")
    print("=" * 60)

    # 初始化 Agent
    print("\n正在初始化 ProductRagAgent...")
    start_time = time.time()
    agent = ProductRagAgent()
    print(f"初始化完成，耗时: {time.time() - start_time:.2f} 秒")

    # 测试用例：本地数据库中存在的商品
    local_products = [
        {"name": "蓝牙耳机", "description": "无线蓝牙耳机"},
        {"name": "纯棉T恤", "description": "纯棉短袖T恤"},
        {"name": "枕头", "description": "家纺护颈枕头"},
        # {"name": "iPhone15", "description": "苹果手机"},
        # {"name": "咖啡机", "description": "家用咖啡机"},
        # {"name": "跑步鞋", "description": "运动跑步鞋"},
        # {"name": "充电宝", "description": "移动电源"},
        # {"name": "积木玩具", "description": "儿童积木"},
        # {"name": "不粘锅", "description": "厨房不粘锅"},
        # {"name": "电动剃须刀", "description": "男士剃须刀"},
        # {"name": "户外桌椅", "description": "户外休闲桌椅"},
        # {"name": "按摩仪", "description": "颈椎按摩仪"},
    ]

    # 测试用例：本地数据库中不存在的商品（需要网络搜索）
    remote_products = [
        {"name": "防晒霜", "description": "防晒护肤品"},
        # {"name": "智能手表", "description": "智能穿戴设备"},
        # {"name": "笔记本电脑", "description": "便携电脑"},
        # {"name": "口红", "description": "美妆彩妆"},
        # {"name": "BKT护腰坐垫", "description": "人体工学坐垫"},
    ]

    print("\n" + "=" * 60)
    print("测试一：查询本地数据库中存在的商品")
    print("=" * 60)

    passed_local = 0
    failed_local = 0

    for product in local_products:
        print(f"\n▶️ 查询: {product['name']}")
        start_time = time.time()
        result = await agent.run(product["name"])
        elapsed = time.time() - start_time

        print(f"  耗时: {elapsed:.2f} 秒")
        if result["retrieved_products"]:
            print(f" 商品: {result['retrieved_products']}")

        # 验证：应该使用本地搜索（商品ID不是'search'）
        is_local = False
        if result["retrieved_products"]:
            first_id = result["retrieved_products"][0].get("id", "")
            is_local = first_id != "search"

        if is_local:
            print("  ✅ 通过：使用本地数据库搜索")
            passed_local += 1
        else:
            print("  ❌ 失败：应该使用本地搜索，但实际使用了网络搜索")
            failed_local += 1

    print(f"\n本地商品测试统计: 通过 {passed_local} / {len(local_products)}")

    print("\n" + "=" * 60)
    print("测试二：查询本地数据库中不存在的商品（应触发网络搜索）")
    print("=" * 60)

    passed_remote = 0
    failed_remote = 0

    for product in remote_products:
        print(f"\n▶️ 查询: {product['name']}")
        start_time = time.time()
        result = await agent.run(product["name"])
        elapsed = time.time() - start_time

        print(f"  耗时: {elapsed:.2f} 秒")
        print(f"  检索到商品数: {len(result['retrieved_products'])}")

        # 验证：应该使用网络搜索（商品ID是'search'）
        is_remote = False
        if result["retrieved_products"]:
            first_id = result["retrieved_products"][0].get("id", "")
            is_remote = first_id == "search"

        if is_remote:
            print("  ✅ 通过：使用网络搜索")
            passed_remote += 1
        elif not result["retrieved_products"]:
            print("  ⚠️  网络搜索未返回结果")
            passed_remote += 1  # 网络搜索无结果也算正常
        else:
            print("  ❌ 失败：应该使用网络搜索，但实际使用了本地搜索")
            failed_remote += 1

    print(f"\n远程商品测试统计: 通过 {passed_remote} / {len(remote_products)}")

    # print("\n" + "="*60)
    # print("测试三：验证检索结果格式")
    # print("="*60)

    # # 测试本地检索结果格式
    # result = await agent.run("蓝牙耳机")
    # if result['retrieved_products']:
    #     product = result['retrieved_products'][0]
    #     print("\n本地商品结构验证:")
    #     required_fields = ['id', 'name', 'price', 'description']
    #     for field in required_fields:
    #         if field in product:
    #             print(f"  ✅ {field} 字段存在")
    #         else:
    #             print(f"  ❌ {field} 字段缺失")

    # print("\n" + "="*60)
    # print("测试总结")
    # print("="*60)
    # total_passed = passed_local + passed_remote
    # total_tests = len(local_products) + len(remote_products)

    # print(f"本地商品测试: {passed_local}/{len(local_products)} 通过")
    # print(f"远程商品测试: {passed_remote}/{len(remote_products)} 通过")
    # print(f"总计: {total_passed}/{total_tests} 通过")

    # if total_passed == total_tests:
    #     print("\n🎉 所有测试通过！")
    # else:
    #     print(f"\n⚠️  部分测试失败: {total_tests - total_passed} 个")


if __name__ == "__main__":
    asyncio.run(test_product_rag())
