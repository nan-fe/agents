import asyncio
import time
import os
from app.agents.product_rag_agent import ProductRagAgent
from app.config import settings

async def test_product_rag():
    # 初始化 ProductRagAgent
    print("正在初始化 ProductRagAgent...")
    print(f"当前使用模型: {settings.EMBEDING_MODEL}")
    
    # 检查是否需要删除旧的向量库
    chroma_path = "./chroma_taobao_v1"
    if os.path.exists(chroma_path):
        print(f"⚠️  检测到旧的向量库: {chroma_path}")
        print("⚠️  切换模型后需要删除旧向量库，否则会使用旧模型的向量数据")
        print(f"⚠️  删除命令: rm -rf {chroma_path}")
    else:
        print("未检测到旧向量库，将创建新的向量库")
    
    start_time = time.time()
    agent = ProductRagAgent()
    print(f"初始化完成，耗时: {time.time() - start_time:.2f} 秒")
    
    # 测试1：查询本地向量库中存在的商品
    print("\n测试1：查询本地向量库中存在的商品")
    print("正在查询 '蓝牙耳机'...")
    start_time = time.time()
    result1 = await agent.run("蓝牙耳机")
    print(f"查询完成，耗时: {time.time() - start_time:.2f} 秒")
    print(f"查询: {result1['query']}")
    print(f"检索到的商品: {result1['retrieved_products']}")
    print(f"回答: {result1['answer']}")
    # 验证是否使用本地搜索（本地搜索的商品有详细信息）
    assert len(result1['retrieved_products']) > 0, "应该检索到商品"
    assert 'id' in result1['retrieved_products'][0], "本地搜索的商品应该有id字段"
    assert 'name' in result1['retrieved_products'][0], "本地搜索的商品应该有name字段"
    assert 'price' in result1['retrieved_products'][0], "本地搜索的商品应该有price字段"
    assert result1['retrieved_products'][0].get('id') != 'search', "不应该是网络搜索结果"
    print("✅ 验证通过：使用了本地搜索")
    print()
    
    # 测试2：查询本地向量库中不存在的商品（应该使用网络搜索）
    print("\n测试2：查询本地向量库中不存在的商品")
    print("正在查询 '防晒霜'...")
    start_time = time.time()
    result2 = await agent.run("防晒霜")
    print(f"查询完成，耗时: {time.time() - start_time:.2f} 秒")
    print(f"查询: {result2['query']}")
    print(f"检索到的商品: {result2['retrieved_products']}")
    print(f"回答: {result2['answer']}")
    # 验证是否使用网络搜索（网络搜索的商品id为'search'）
    if result2['retrieved_products']:
        assert result2['retrieved_products'][0].get('id') == 'search', "应该是网络搜索结果"
        print("✅ 验证通过：使用了网络搜索")
    else:
        print("⚠️  网络搜索未返回结果")
    print()
    
    
    # 测试4：查询本地向量库中的商品 - 纯棉T恤
    print("\n测试4：查询本地向量库中的商品 - 纯棉T恤")
    print("正在查询 '纯棉T恤'...")
    start_time = time.time()
    result4 = await agent.run("纯棉T恤")
    print(f"查询完成，耗时: {time.time() - start_time:.2f} 秒")
    print(f"查询: {result4['query']}")
    print(f"检索到的商品: {result4['retrieved_products']}")
    print(f"回答: {result4['answer']}")
    # 验证是否使用本地搜索
    assert len(result4['retrieved_products']) > 0, "应该检索到商品"
    assert 'id' in result4['retrieved_products'][0], "本地搜索的商品应该有id字段"
    assert 'name' in result4['retrieved_products'][0], "本地搜索的商品应该有name字段"
    assert 'price' in result4['retrieved_products'][0], "本地搜索的商品应该有price字段"
    assert result4['retrieved_products'][0].get('id') != 'search', "不应该是网络搜索结果"
    print("✅ 验证通过：使用了本地搜索")
    print()
    
    # 测试5：查询本地向量库中的商品 - iPhone15
    print("\n测试5：查询本地向量库中的商品 - iPhone15")
    print("正在查询 'iPhone15'...")
    start_time = time.time()
    result5 = await agent.run("iPhone15")
    print(f"查询完成，耗时: {time.time() - start_time:.2f} 秒")
    print(f"查询: {result5['query']}")
    print(f"检索到的商品: {result5['retrieved_products']}")
    print(f"回答: {result5['answer']}")
    # 验证是否使用本地搜索
    assert len(result5['retrieved_products']) > 0, "应该检索到商品"
    assert 'id' in result5['retrieved_products'][0], "本地搜索的商品应该有id字段"
    assert 'name' in result5['retrieved_products'][0], "本地搜索的商品应该有name字段"
    assert 'price' in result5['retrieved_products'][0], "本地搜索的商品应该有price字段"
    assert result5['retrieved_products'][0].get('id') != 'search', "不应该是网络搜索结果"
    print("✅ 验证通过：使用了本地搜索")
    print()
    
    # 测试6：查询本地向量库中的商品 - 咖啡机
    print("\n测试6：查询本地向量库中的商品 - 咖啡机")
    print("正在查询 '咖啡机'...")
    start_time = time.time()
    result6 = await agent.run("咖啡机")
    print(f"查询完成，耗时: {time.time() - start_time:.2f} 秒")
    print(f"查询: {result6['query']}")
    print(f"检索到的商品: {result6['retrieved_products']}")
    print(f"回答: {result6['answer']}")
    # 验证是否使用本地搜索
    assert len(result6['retrieved_products']) > 0, "应该检索到商品"
    assert 'id' in result6['retrieved_products'][0], "本地搜索的商品应该有id字段"
    assert 'name' in result6['retrieved_products'][0], "本地搜索的商品应该有name字段"
    assert 'price' in result6['retrieved_products'][0], "本地搜索的商品应该有price字段"
    assert result6['retrieved_products'][0].get('id') != 'search', "不应该是网络搜索结果"
    print("✅ 验证通过：使用了本地搜索")
    print()
    
    # 测试7：查询本地向量库中的商品 - 跑步鞋
    print("\n测试7：查询本地向量库中的商品 - 跑步鞋")
    print("正在查询 '跑步鞋'...")
    start_time = time.time()
    result7 = await agent.run("跑步鞋")
    print(f"查询完成，耗时: {time.time() - start_time:.2f} 秒")
    print(f"查询: {result7['query']}")
    print(f"检索到的商品: {result7['retrieved_products']}")
    print(f"回答: {result7['answer']}")
    # 验证是否使用本地搜索
    assert len(result7['retrieved_products']) > 0, "应该检索到商品"
    assert 'id' in result7['retrieved_products'][0], "本地搜索的商品应该有id字段"
    assert 'name' in result7['retrieved_products'][0], "本地搜索的商品应该有name字段"
    assert 'price' in result7['retrieved_products'][0], "本地搜索的商品应该有price字段"
    assert result7['retrieved_products'][0].get('id') != 'search', "不应该是网络搜索结果"
    print("✅ 验证通过：使用了本地搜索")
    print()
    
    # 测试8：查询本地向量库中的商品 - 充电宝
    print("\n测试8：查询本地向量库中的商品 - 充电宝")
    print("正在查询 '充电宝'...")
    start_time = time.time()
    result8 = await agent.run("充电宝")
    print(f"查询完成，耗时: {time.time() - start_time:.2f} 秒")
    print(f"查询: {result8['query']}")
    print(f"检索到的商品: {result8['retrieved_products']}")
    print(f"回答: {result8['answer']}")
    # 验证是否使用本地搜索
    assert len(result8['retrieved_products']) > 0, "应该检索到商品"
    assert 'id' in result8['retrieved_products'][0], "本地搜索的商品应该有id字段"
    assert 'name' in result8['retrieved_products'][0], "本地搜索的商品应该有name字段"
    assert 'price' in result8['retrieved_products'][0], "本地搜索的商品应该有price字段"
    assert result8['retrieved_products'][0].get('id') != 'search', "不应该是网络搜索结果"
    print("✅ 验证通过：使用了本地搜索")
    print()
    
    # 测试9：查询本地向量库中的商品 - 积木玩具
    print("\n测试9：查询本地向量库中的商品 - 积木玩具")
    print("正在查询 '积木玩具'...")
    start_time = time.time()
    result9 = await agent.run("积木玩具")
    print(f"查询完成，耗时: {time.time() - start_time:.2f} 秒")
    print(f"查询: {result9['query']}")
    print(f"检索到的商品: {result9['retrieved_products']}")
    print(f"回答: {result9['answer']}")
    # 验证是否使用本地搜索
    assert len(result9['retrieved_products']) > 0, "应该检索到商品"
    assert 'id' in result9['retrieved_products'][0], "本地搜索的商品应该有id字段"
    assert 'name' in result9['retrieved_products'][0], "本地搜索的商品应该有name字段"
    assert 'price' in result9['retrieved_products'][0], "本地搜索的商品应该有price字段"
    assert result9['retrieved_products'][0].get('id') != 'search', "不应该是网络搜索结果"
    print("✅ 验证通过：使用了本地搜索")
    print()
    
    # 测试10：查询本地向量库中的商品 - 不粘锅
    print("\n测试10：查询本地向量库中的商品 - 不粘锅")
    print("正在查询 '不粘锅'...")
    start_time = time.time()
    result10 = await agent.run("不粘锅")
    print(f"查询完成，耗时: {time.time() - start_time:.2f} 秒")
    print(f"查询: {result10['query']}")
    print(f"检索到的商品: {result10['retrieved_products']}")
    print(f"回答: {result10['answer']}")
    # 验证是否使用本地搜索
    assert len(result10['retrieved_products']) > 0, "应该检索到商品"
    assert 'id' in result10['retrieved_products'][0], "本地搜索的商品应该有id字段"
    assert 'name' in result10['retrieved_products'][0], "本地搜索的商品应该有name字段"
    assert 'price' in result10['retrieved_products'][0], "本地搜索的商品应该有price字段"
    assert result10['retrieved_products'][0].get('id') != 'search', "不应该是网络搜索结果"
    print("✅ 验证通过：使用了本地搜索")
    print()
    
    # 测试11：查询本地向量库中的商品 - 电动剃须刀
    print("\n测试11：查询本地向量库中的商品 - 电动剃须刀")
    print("正在查询 '电动剃须刀'...")
    start_time = time.time()
    result11 = await agent.run("电动剃须刀")
    print(f"查询完成，耗时: {time.time() - start_time:.2f} 秒")
    print(f"查询: {result11['query']}")
    print(f"检索到的商品: {result11['retrieved_products']}")
    print(f"回答: {result11['answer']}")
    # 验证是否使用本地搜索
    assert len(result11['retrieved_products']) > 0, "应该检索到商品"
    assert 'id' in result11['retrieved_products'][0], "本地搜索的商品应该有id字段"
    assert 'name' in result11['retrieved_products'][0], "本地搜索的商品应该有name字段"
    assert 'price' in result11['retrieved_products'][0], "本地搜索的商品应该有price字段"
    assert result11['retrieved_products'][0].get('id') != 'search', "不应该是网络搜索结果"
    print("✅ 验证通过：使用了本地搜索")
    print()
    
    # 测试12：查询本地向量库中的商品 - 户外桌椅
    print("\n测试12：查询本地向量库中的商品 - 户外桌椅")
    print("正在查询 '户外桌椅'...")
    start_time = time.time()
    result12 = await agent.run("户外桌椅")
    print(f"查询完成，耗时: {time.time() - start_time:.2f} 秒")
    print(f"查询: {result12['query']}")
    print(f"检索到的商品: {result12['retrieved_products']}")
    print(f"回答: {result12['answer']}")
    # 验证是否使用本地搜索
    assert len(result12['retrieved_products']) > 0, "应该检索到商品"
    assert 'id' in result12['retrieved_products'][0], "本地搜索的商品应该有id字段"
    assert 'name' in result12['retrieved_products'][0], "本地搜索的商品应该有name字段"
    assert 'price' in result12['retrieved_products'][0], "本地搜索的商品应该有price字段"
    assert result12['retrieved_products'][0].get('id') != 'search', "不应该是网络搜索结果"
    print("✅ 验证通过：使用了本地搜索")
    print()
    
    # 测试13：查询本地向量库中的商品 - 按摩仪
    print("\n测试13：查询本地向量库中的商品 - 按摩仪")
    print("正在查询 '按摩仪'...")
    start_time = time.time()
    result13 = await agent.run("按摩仪")
    print(f"查询完成，耗时: {time.time() - start_time:.2f} 秒")
    print(f"查询: {result13['query']}")
    print(f"检索到的商品: {result13['retrieved_products']}")
    print(f"回答: {result13['answer']}")
    # 验证是否使用本地搜索
    assert len(result13['retrieved_products']) > 0, "应该检索到商品"
    assert 'id' in result13['retrieved_products'][0], "本地搜索的商品应该有id字段"
    assert 'name' in result13['retrieved_products'][0], "本地搜索的商品应该有name字段"
    assert 'price' in result13['retrieved_products'][0], "本地搜索的商品应该有price字段"
    assert result13['retrieved_products'][0].get('id') != 'search', "不应该是网络搜索结果"
    print("✅ 验证通过：使用了本地搜索")
    print()
    
    # 测试14：查询本地向量库中不存在的商品 - 防晒霜
    print("\n测试14：查询本地向量库中不存在的商品 - 防晒霜")
    print("正在查询 '防晒霜'...")
    start_time = time.time()
    result14 = await agent.run("防晒霜")
    print(f"查询完成，耗时: {time.time() - start_time:.2f} 秒")
    print(f"查询: {result14['query']}")
    print(f"检索到的商品: {result14['retrieved_products']}")
    print(f"回答: {result14['answer']}")
    # 验证是否使用网络搜索
    if result14['retrieved_products']:
        assert result14['retrieved_products'][0].get('id') == 'search', "应该是网络搜索结果"
        print("✅ 验证通过：使用了网络搜索")
    else:
        print("⚠️  网络搜索未返回结果")
    print()
    
    # 测试15：查询本地向量库中不存在的商品 - 智能手表
    print("\n测试15：查询本地向量库中不存在的商品 - 智能手表")
    print("正在查询 '智能手表'...")
    start_time = time.time()
    result15 = await agent.run("智能手表")
    print(f"查询完成，耗时: {time.time() - start_time:.2f} 秒")
    print(f"查询: {result15['query']}")
    print(f"检索到的商品: {result15['retrieved_products']}")
    print(f"回答: {result15['answer']}")
    # 验证是否使用网络搜索
    if result15['retrieved_products']:
        assert result15['retrieved_products'][0].get('id') == 'search', "应该是网络搜索结果"
        print("✅ 验证通过：使用了网络搜索")
    else:
        print("⚠️  网络搜索未返回结果")
    print()
    
    # 测试16：查询本地向量库中不存在的商品 - 笔记本电脑
    print("\n测试16：查询本地向量库中不存在的商品 - 笔记本电脑")
    print("正在查询 '笔记本电脑'...")
    start_time = time.time()
    result16 = await agent.run("笔记本电脑")
    print(f"查询完成，耗时: {time.time() - start_time:.2f} 秒")
    print(f"查询: {result16['query']}")
    print(f"检索到的商品: {result16['retrieved_products']}")
    print(f"回答: {result16['answer']}")
    # 验证是否使用网络搜索
    if result16['retrieved_products']:
        assert result16['retrieved_products'][0].get('id') == 'search', "应该是网络搜索结果"
        print("✅ 验证通过：使用了网络搜索")
    else:
        print("⚠️  网络搜索未返回结果")
    print()
    
    # 测试17：查询本地向量库中不存在的商品 - 口红
    print("\n测试17：查询本地向量库中不存在的商品 - 口红")
    print("正在查询 '口红'...")
    start_time = time.time()
    result17 = await agent.run("口红")
    print(f"查询完成，耗时: {time.time() - start_time:.2f} 秒")
    print(f"查询: {result17['query']}")
    print(f"检索到的商品: {result17['retrieved_products']}")
    print(f"回答: {result17['answer']}")
    # 验证是否使用网络搜索
    if result17['retrieved_products']:
        assert result17['retrieved_products'][0].get('id') == 'search', "应该是网络搜索结果"
        print("✅ 验证通过：使用了网络搜索")
    else:
        print("⚠️  网络搜索未返回结果")
    print()

    print("\n测试18：查询本地向量库中不存在的商品 -BKT护腰坐垫")
    print("正在查询 'BKT护腰坐垫'...")
    start_time = time.time()
    result18 = await agent.run("BKT护腰坐垫")
    print(f"查询完成，耗时: {time.time() - start_time:.2f} 秒")
    print(f"查询: {result18['query']}")
    print(f"检索到的商品: {result18['retrieved_products']}")
    print(f"回答: {result18['answer']}")
    # 验证是否使用网络搜索
    if result18['retrieved_products']:
        assert result18['retrieved_products'][0].get('id') == 'search', "应该是网络搜索结果"
        print("✅ 验证通过：使用了网络搜索")
    else:
        print("⚠️  网络搜索未返回结果")
    print()
    
async def test_retrieved_products():
    """测试检索到的商品是否符合预期"""
    # 测试19：测试 retrieve 方法的检索能力
    
    print(f"当前使用模型: {settings.RANKER_MODEL}")
    
    # 检查是否需要删除旧的向量库
    chroma_path = "./chroma_taobao_v1"
    if os.path.exists(chroma_path):
        print(f"⚠️  检测到旧的向量库: {chroma_path}")
        print("⚠️  切换模型后需要删除旧向量库，否则会使用旧模型的向量数据")
        print(f"⚠️  删除命令: rm -rf {chroma_path}")
    else:
        print("未检测到旧向量库，将创建新的向量库")
    print("\n测试19：测试 retrieve 方法的检索能力")
    print("正在直接调用 retrieve 方法...")
    agent = ProductRagAgent()
    # 测试19.1：测试精确匹配
    print("\n19.1 测试精确匹配 - '蓝牙耳机'")
    retrieve_result1 = agent.retrieve("蓝牙耳机", top_k=3)
    print(f"检索到 {len(retrieve_result1)} 个商品")
    for i, product in enumerate(retrieve_result1):
        print(f"  {i+1}. {product['name']} | 相似度: {product['similarity']:.4f}| 关键词: {product.get('bm25_score', 0):.4f}")
    assert len(retrieve_result1) > 0, "应该检索到商品"
    assert all('similarity' in p for p in retrieve_result1), "所有商品都应该有相似度字段"
    print("✅ 验证通过：精确匹配测试")
    
    # 测试19.2：测试部分匹配
    print("\n19.2 测试部分匹配 - '耳机'")
    retrieve_result2 = agent.retrieve("耳机", top_k=3)
    print(f"检索到 {len(retrieve_result2)} 个商品")
    for i, product in enumerate(retrieve_result2):
        print(f"  {i+1}. {product['name']} | 相似度: {product['similarity']:.4f}| BM25分数: {product.get('bm25_score', 0):.4f}")
    assert len(retrieve_result2) > 0, "应该检索到商品"
    print("✅ 验证通过：部分匹配测试")
    
    # 测试19.3：测试同义词匹配
    print("\n19.3 测试同义词匹配 - '运动跑鞋'")
    retrieve_result3 = agent.retrieve("运动跑鞋", top_k=3)
    print(f"检索到 {len(retrieve_result3)} 个商品")
    for i, product in enumerate(retrieve_result3):
        print(f"  {i+1}. {product['name']} | 相似度: {product['similarity']:.4f}| BM25分数: {product.get('bm25_score', 0):.4f}")
    assert len(retrieve_result3) > 0, "应该检索到商品"
    print("✅ 验证通过：同义词匹配测试")
    
    # 测试19.4：测试 top_k 参数
    print("\n19.4 测试 top_k 参数")
    retrieve_result4 = agent.retrieve("手机", top_k=1)
    assert len(retrieve_result4) == 1, "top_k=1 应该只返回1个商品"
    retrieve_result5 = agent.retrieve("手机", top_k=5)
    assert len(retrieve_result5) <= 5, "top_k=5 应该最多返回5个商品"
    print("✅ 验证通过：top_k 参数测试")
    

    # 测试19.6：测试 BM25 关键词检索
    print("\n19.6 测试重排序 蓝牙耳机")
    retrieve_result7 = agent.retrieve("蓝牙耳机", top_k=3)
    print(f"检索到 {len(retrieve_result7)} 个商品")
    for i, product in enumerate(retrieve_result7):
        print(f"  {i+1}. {product['name']} | 相似度: {product['similarity']:.4f} | BM25分数: {product.get('bm25_score', 0):.4f} | 排序分数: {product.get('rank_score', 0):.4f}")
    assert len(retrieve_result7) > 0, "应该检索到商品"
    assert any('bm25_score' in p for p in retrieve_result7), "至少有一个商品应该有 BM25 分数"
    print("✅ 验证通过：测试重排序测试")

    print("\n19.6 测试重排序 BKT护腰坐垫")
    retrieve_result8 = agent.retrieve("BKT护腰坐垫", top_k=3)
    print(f"检索到 {len(retrieve_result8)} 个商品")
    for i, product in enumerate(retrieve_result8):
        print(f"  {i+1}. {product['name']} | 相似度: {product['similarity']:.4f} | BM25分数: {product.get('bm25_score', 0):.4f} | 排序分数: {product.get('rank_score', 0):.4f}")
    assert len(retrieve_result8) > 0, "应该检索到商品"
    assert any('bm25_score' in p for p in retrieve_result8), "至少有一个商品应该有 BM25 分数"
    print("✅ 验证通过：测试重排序测试")

    print("\n19.6 测试重排序 口红")
    retrieve_result9 = agent.retrieve("口红", top_k=3)
    print(f"检索到 {len(retrieve_result9)} 个商品")
    for i, product in enumerate(retrieve_result9):
        print(f"  {i+1}. {product['name']} | 相似度: {product['similarity']:.4f} | BM25分数: {product.get('bm25_score', 0):.4f} | 排序分数: {product.get('rank_score', 0):.4f}")
    assert len(retrieve_result9) > 0, "应该检索到商品"
    assert any('bm25_score' in p for p in retrieve_result9), "至少有一个商品应该有 BM25 分数"
    print("✅ 验证通过：测试重排序测试")

    print("\n19.6 测试重排序 运动跑鞋")
    retrieve_result10 = agent.retrieve("运动跑鞋", top_k=3)
    print(f"检索到 {len(retrieve_result10)} 个商品")
    for i, product in enumerate(retrieve_result10):
        print(f"  {i+1}. {product['name']} | 相似度: {product['similarity']:.4f} | BM25分数: {product.get('bm25_score', 0):.4f} | 排序分数: {product.get('rank_score', 0):.4f}")
    assert len(retrieve_result10) > 0, "应该检索到商品"
    assert any('bm25_score' in p for p in retrieve_result10), "至少有一个商品应该有 BM25 分数"
    print("✅ 验证通过：测试重排序测试")
    
if __name__ == "__main__":
    # asyncio.run(test_product_rag())
    asyncio.run(test_retrieved_products())