from ddgs import DDGS
from typing import List, Dict, Any
from langchain_community.tools import DuckDuckGoSearchRun


def search_duckduckgo(query: str, max_results: int = 5, site: str = None) -> List[Dict[str, Any]]:
    """
    使用 DuckDuckGo 搜索获取相关信息
    
    Args:
        query: 搜索查询词
        max_results: 最大返回结果数
        site: 限定的网站域名，如 "taobao.com"
        
    Returns:
        搜索结果列表，每个结果包含标题、链接和摘要
    """
    try:
        with DDGS() as ddgs:
            # 构建搜索查询
            search_query = query
            if site:
                search_query = f"{query} site:{site}"
                
            results = []
            for result in ddgs.text(search_query, max_results=max_results):
                results.append({
                    "title": result.get("title", ""),
                    "url": result.get("href", ""),
                    "snippet": result.get("body", "")
                })
            return results
    except Exception as e:
        print(f"搜索出错: {str(e)}")
        return []


def search_news(query: str, max_results: int = 3) -> List[Dict[str, Any]]:
    """
    使用 DuckDuckGo 搜索获取新闻信息
    
    Args:
        query: 搜索查询词
        max_results: 最大返回结果数
        
    Returns:
        新闻结果列表，每个结果包含标题、链接、摘要和日期
    """
    try:
        with DDGS() as ddgs:
            results = []
            for result in ddgs.news(query, max_results=max_results):
                results.append({
                    "title": result.get("title", ""),
                    "url": result.get("url", ""),
                    "snippet": result.get("body", ""),
                    "date": result.get("date", "")
                })
            return results
    except Exception as e:
        print(f"新闻搜索出错: {str(e)}")
        return []


def search_images(query: str, max_results: int = 3) -> List[Dict[str, Any]]:
    """
    使用 DuckDuckGo 搜索获取图片信息
    
    Args:
        query: 搜索查询词
        max_results: 最大返回结果数
        
    Returns:
        图片结果列表，每个结果包含标题、图片URL和来源URL
    """
    try:
        with DDGS() as ddgs:
            results = []
            for result in ddgs.images(query, max_results=max_results):
                results.append({
                    "title": result.get("title", ""),
                    "image_url": result.get("image", ""),
                    "source_url": result.get("url", "")
                })
            return results
    except Exception as e:
        print(f"图片搜索出错: {str(e)}")
        return []


def search_duckduckgo_langchain(query: str, site: str = "taobao.com"):
    """
    使用 LangChain 的 DuckDuckGoSearchRun 搜索特定网站
    
    Args:
        query: 搜索查询词
        site: 限定的网站域名
        
    Returns:
        搜索结果文本
    """
    try:
        search = DuckDuckGoSearchRun()
        full_query = f"{query} site:{site}"
        result = search.run(full_query)
        return result
    except Exception as e:
        print(f"LangChain 搜索出错: {str(e)}")
        return ""


if __name__ == "__main__":
    # 测试搜索功能
    query = "按摩器"
    print(f"搜索: {query}")
    
    # 测试文本搜索
    print("\n文本搜索结果:")
    text_results = search_duckduckgo(query,2,"www.taobao.com")
    for i, result in enumerate(text_results):
        print(f"{i+1}. {result['title']}")
        print(f"   URL: {result['url']}")
        print(f"   摘要: {result['snippet'][:100]}...")
    
    # # 测试新闻搜索
    # print("\n新闻搜索结果:")
    # news_results = search_news(query)
    # for i, result in enumerate(news_results):
    #     print(f"{i+1}. {result['title']}")
    #     print(f"   URL: {result['url']}")
    #     print(f"   日期: {result['date']}")
    
    # # 测试图片搜索
    # print("\n图片搜索结果:")
    # image_results = search_images(query)
    # for i, result in enumerate(image_results):
    #     print(f"{i+1}. {result['title']}")
    #     print(f"   图片URL: {result['image_url']}")
    #     print(f"   来源URL: {result['source_url']}")
    
    # 测试 LangChain 搜索
    print("\nLangChain 搜索结果 (淘宝):")
    langchain_result = search_duckduckgo_langchain("运动鞋 男")
    print(langchain_result)