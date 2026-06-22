# from app.utils.search_tool import get_product_details_with_selenium

# # 测试商品详情页抓取
# print("测试 selenium 商品详情抓取...")

# # 测试链接（使用用户提供的京东商品链接）
# test_urls = [
#     "https://item.jd.com/100142621662.html?spm=aTagYTAyMjAuYwMlQjYMC5jMDMwMDU1MDYyMA",  # 用户提供的京东商品链接
#     # "https://item.taobao.com/item.htm?id=656006185714"  # 淘宝商品链接
# ]

# for url in test_urls:
#     print(f"\n测试 URL: {url}")
#     print("抓取中...")
#     details = get_product_details_with_selenium(url)

#     if details:
#         print("\n抓取结果:")
#         for key, value in details.items():
#             if key == 'images':
#                 print(f"{key}: {len(value)} 张图片")
#                 for i, img in enumerate(value[:3]):  # 只显示前3张图片
#                     print(f"  {i+1}. {img}")
#             else:
#                 print(f"{key}: {value}")
#     else:
#         print("抓取失败")

# print("\n测试完成！")
