from app.utils.search_tool import search_duckduckgo,get_product_specs

# 测试普通搜索
print("search_duckduckgo_langchain '伊丽莎白雅顿绿茶身体乳':")
results = get_product_specs("伊丽莎白雅顿绿茶身体乳")
print(results)
# for i, result in enumerate(results):
#     print(f"{i+1}. {result['title']}")
#     print(f"   URL: {result['url']}")
#     print(f"   摘要: {result['snippet'][:100]}...")

# 测试限定网站搜索
print("\nsearch_duckduckgo '伊丽莎白雅顿绿茶身体乳':")
results = search_duckduckgo("伊丽莎白雅顿绿茶身体乳")
print(results)      
for i, result in enumerate(results):
    print(f"{i+1}. {result['title']}")
    print(f"   URL: {result['url']}")
    print(f"   摘要: {result['snippet'][:100]}...")