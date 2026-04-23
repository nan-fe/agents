import re
from urllib.parse import urlparse, parse_qs
from ddgs import DDGS
from typing import List, Dict, Any
from langchain_community.tools import DuckDuckGoSearchRun
import requests
from bs4 import BeautifulSoup
import json
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException

def extract_product_params(url: str) -> Dict[str, Any]:
    """
    从 URL 中提取商品参数信息
    
    Args:
        url: 商品链接 URL
        
    Returns:
        提取的商品参数字典
    """
    params = {}
    
    try:
        # 解析 URL
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)
        
        # 处理淘宝 URL
        if 'taobao.com' in parsed_url.netloc:
            # 处理 pcdetail.taobao.com 链接（会重定向）
            if 'pcdetail.taobao.com' in parsed_url.netloc:
                params['url_type'] = 'taobao_pcdetail'
                params['note'] = '该链接会重定向到标准商品页面'
                
                # 尝试从 URL 路径中提取可能的参数
                path = parsed_url.path
                if path and path.endswith('.html'):
                    # 提取文件名部分（可能包含编码的商品信息）
                    filename = path.split('/')[-1].replace('.html', '')
                    params['encoded_params'] = filename
            
            # 提取商品 ID
            item_id_match = re.search(r'id=(\d+)', url)
            if item_id_match:
                params['item_id'] = item_id_match.group(1)
            
            # 提取店铺 ID
            shop_id_match = re.search(r'shop_id=(\d+)', url)
            if shop_id_match:
                params['shop_id'] = shop_id_match.group(1)
            
            # 提取其他参数
            for key, value in query_params.items():
                if key in ['id', 'shop_id', 'spm', 'scm']:
                    params[key] = value[0]
        
        # 处理京东 URL
        elif 'jd.com' in parsed_url.netloc:
            # 提取商品 ID
            product_id_match = re.search(r'/(\d+)\.html', url)
            if product_id_match:
                params['product_id'] = product_id_match.group(1)
        
        # 处理天猫 URL
        elif 'tmall.com' in parsed_url.netloc:
            # 提取商品 ID
            item_id_match = re.search(r'id=(\d+)', url)
            if item_id_match:
                params['item_id'] = item_id_match.group(1)
        
        # 通用参数提取
        if 'q' in query_params:
            params['search_query'] = query_params['q'][0]
        
    except Exception as e:
        print(f"提取参数出错: {str(e)}")
    
    return params


def search_duckduckgo(query: str, max_results: int = 5, site: str = None) -> List[Dict[str, Any]]:
    """
    使用 DuckDuckGo 搜索获取相关信息，并从 URL 中提取商品参数
    
    Args:
        query: 搜索查询词
        max_results: 最大返回结果数
        site: 限定的网站域名，如 "taobao.com"
        
    Returns:
        搜索结果列表，每个结果包含标题、链接、摘要和商品参数
    """
    try:
        with DDGS() as ddgs:
            # 构建搜索查询
            search_query = query
            if site:
                search_query = f"{query} site:{site}"
                
            results = []
            for result in ddgs.text(search_query, max_results=max_results):
                print('originaltext', result)
                url = result.get("href", "")
                # 提取商品参数
                product_params = extract_product_params(url)
                
                results.append({
                    "title": result.get("title", ""),
                    "url": url,
                    "snippet": result.get("body", ""),
                    "product_params": product_params  # 添加商品参数
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
        # 优先使用我们自己的搜索函数，因为它能提取商品参数
        results = search_duckduckgo(query, max_results=5, site=site)
        
        # 构建结果文本
        result_text = ""
        for i, result in enumerate(results):
            result_text += f"{i+1}. {result['title']}\n"
            result_text += f"   URL: {result['url']}\n"
            if result.get('product_params'):
                result_text += f"   商品参数: {result['product_params']}\n"
            result_text += f"   摘要: {result['snippet']}\n\n"
        
        return result_text
    except Exception as e:
        print(f"LangChain 搜索出错: {str(e)}")
        # 回退到原始的 LangChain 搜索
        try:
            search = DuckDuckGoSearchRun()
            full_query = f"{query} site:{site}"
            result = search.run(full_query)
            return result
        except:
            return ""


def get_product_specs(product_name):
    # 1. 构建精准搜索查询
    query = f'"{product_name}" 规格参数 site:jd.com OR site:taobao.com'
    with DDGS() as ddgs:
        search_results = ddgs.text(query, max_results=3)
        if not search_results:
            return None

        # 2. 获取第一个结果的页面内容
        target_url = search_results[0]['href']
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        try:
            response = requests.get(target_url, headers=headers, timeout=10)
            response.raise_for_status()
        except Exception as e:
            print(f"请求失败: {e}")
            return None

        # 3. 解析HTML，提取参数
        soup = BeautifulSoup(response.text, 'html.parser')
        # 示例：尝试从JSON-LD中提取
        json_ld_script = soup.find('script', type='application/ld+json')
        if json_ld_script:
            try:
                data = json.loads(json_ld_script.string)
                return data.get('description', '')  # 假设JSON中包含描述信息
            except:
                pass
        
        # 备选方案：提取商品标题和描述
        title = soup.find('title').get_text(strip=True) if soup.find('title') else '无标题'
        # 使用 .get_text() 提取纯文本并清理
        description = soup.find('meta', {'name': 'description'})
        description_content = description['content'] if description else '无描述'
        return {'title': title, 'description': description_content}


def get_product_details_with_selenium(product_url):
    """
    使用 Selenium 抓取商品详情页信息
    
    Args:
        product_url: 商品详情页 URL
        
    Returns:
        商品详情信息字典
    """
    details = {}
    
    try:
        # 配置 Chrome 浏览器
        chrome_options = Options()
        chrome_options.add_argument('--headless')  # 无头模式
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        
        # 初始化浏览器
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )
        
        # 访问页面，设置页面加载超时
        driver.set_page_load_timeout(10)  # 页面加载超时10秒
        driver.set_script_timeout(10)  # 脚本执行超时10秒
        
        try:
            driver.get(product_url)
            
            # 等待页面加载
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, 'body'))
            )
        except TimeoutException:
            print("页面加载超时，继续处理已加载内容")
            # 即使超时也继续处理，获取已加载的内容
        
        # 获取页面源码
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')
        
        # 提取商品信息
        # 1. 标题
        title = soup.find('title')
        if title:
            details['title'] = title.get_text(strip=True)
        
        # 2. 价格
        # 淘宝/天猫价格
        price_ele = soup.find(class_='tm-price') or soup.find(class_='price') or soup.find(class_='J-p-')
        if price_ele:
            details['price'] = price_ele.get_text(strip=True)
        
        # 3. 商品描述
        description_meta = soup.find('meta', {'name': 'description'})
        if description_meta:
            details['description'] = description_meta.get('content', '')
        
        # 4. 规格参数
        specs = {}
        # 尝试从不同位置提取规格参数
        
        # 京东商品详情页特定处理
        if 'jd.com' in product_url:
            # 查找商品详情标签页内容
            detail_tab = soup.find(class_='tab-con')
            if detail_tab:
                # 查找参数表格
                spec_sections = detail_tab.find_all(class_='Ptable')
                for section in spec_sections:
                    # 查找表格行
                    rows = section.find_all('tr')
                    for row in rows:
                        # 京东的参数表格结构
                        th = row.find('th')
                        tds = row.find_all('td')
                        if th and tds:
                            key = th.get_text(strip=True)
                            # 有些行有多个 td，取第一个
                            value = tds[0].get_text(strip=True)
                            if key and value:
                                specs[key] = value
        else:
            # 其他网站的通用处理
            spec_tables = soup.find_all('table', class_=['attributes-list', 'spec-table'])
            for table in spec_tables:
                rows = table.find_all('tr')
                for row in rows:
                    cols = row.find_all(['th', 'td'])
                    if len(cols) >= 2:
                        key = cols[0].get_text(strip=True)
                        value = cols[1].get_text(strip=True)
                        specs[key] = value
        
        # 如果找到了规格参数，添加到详情中
        if specs:
            details['specs'] = specs
        
        # 5. 商品图片
        images = []
        img_tags = soup.find_all('img')
        for img in img_tags:
            img_url = img.get('src') or img.get('data-src')
            if img_url and 'http' in img_url:
                images.append(img_url)
        if images:
            details['images'] = images[:5]  # 只保存前5张图片
        
        # 6. 商品ID
        if 'taobao.com' in product_url or 'tmall.com' in product_url:
            product_id_match = re.search(r'id=(\d+)', product_url)
            if product_id_match:
                details['product_id'] = product_id_match.group(1)
        elif 'jd.com' in product_url:
            product_id_match = re.search(r'/\d+\.html', product_url)
            if product_id_match:
                details['product_id'] = product_id_match.group(0).strip('/.html')
        
        # 7. URL信息
        details['url'] = product_url
        
        # 关闭浏览器
        driver.quit()
        
    except Exception as e:
        print(f"Selenium 抓取出错: {str(e)}")
        if 'driver' in locals():
            driver.quit()
    
    return details

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