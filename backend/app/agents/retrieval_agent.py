from app.agents.base_agent import BaseAgent
from app.models.schemas import PlanningResult
from typing import Optional, List, Dict, Any
import asyncio
import aiohttp

class ProductInfo:
    """商品信息模型"""
    def __init__(self, title: str, price: str, link: str, image_url: str, platform: str):
        self.title = title
        self.price = price
        self.link = link
        self.image_url = image_url
        self.platform = platform

class RetrievalAgent(BaseAgent):
    """检索Agent"""
    
    def __init__(self):
        """初始化检索Agent"""
        super().__init__("Retrieval", "商品检索专家")
        self.session = None
    
    async def _create_session(self):
        """创建HTTP会话"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def _close_session(self):
        """关闭HTTP会话"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def _search_taobao(self, query: str) -> List[ProductInfo]:
        """搜索淘宝商品
        
        Args:
            query: 搜索关键词
            
        Returns:
            商品信息列表
        """
        # 这里使用模拟数据，实际项目中应该调用淘宝API
        return [
            ProductInfo(
                title="【学生党必备】平价防晒霜 清爽不油腻 SPF50+",
                price="¥69.9",
                link="https://taobao.com/item/123456",
                image_url="https://example.com/taobao1.jpg",
                platform="淘宝"
            ),
            ProductInfo(
                title="防晒霜女学生党平价 面部身体通用 清爽不粘腻",
                price="¥59.9",
                link="https://taobao.com/item/789012",
                image_url="https://example.com/taobao2.jpg",
                platform="淘宝"
            )
        ]
    
    async def _search_jd(self, query: str) -> List[ProductInfo]:
        """搜索京东商品
        
        Args:
            query: 搜索关键词
            
        Returns:
            商品信息列表
        """
        # 这里使用模拟数据，实际项目中应该调用京东API
        return [
            ProductInfo(
                title="京东自营 防晒霜 学生党平价 清爽不油腻",
                price="¥79.9",
                link="https://jd.com/item/345678",
                image_url="https://example.com/jd1.jpg",
                platform="京东"
            ),
            ProductInfo(
                title="防晒霜 SPF50+ 清爽不油腻 学生党专属",
                price="¥69.9",
                link="https://jd.com/item/901234",
                image_url="https://example.com/jd2.jpg",
                platform="京东"
            )
        ]
    
    async def run(self, input_data: str, log_callback: Optional[callable] = None) -> Dict[str, Any]:
        """运行检索Agent
        
        Args:
            input_data: 用户输入的描述
            log_callback: 日志回调函数
            
        Returns:
            检索结果
        """
        await self.log(f"开始检索商品: {input_data}", log_callback)
        
        try:
            # 创建HTTP会话
            await self._create_session()
            
            # 并行搜索淘宝和京东
            taobao_task = self._search_taobao(input_data)
            jd_task = self._search_jd(input_data)
            
            taobao_products, jd_products = await asyncio.gather(
                taobao_task,
                jd_task
            )
            
            # 合并结果
            all_products = taobao_products + jd_products
            
            # 构建返回结果
            result = {
                "query": input_data,
                "total_products": len(all_products),
                "products": [
                    {
                        "title": product.title,
                        "price": product.price,
                        "link": product.link,
                        "image_url": product.image_url,
                        "platform": product.platform
                    }
                    for product in all_products
                ],
                "recommendations": [
                    f"{product.platform}: {product.title} - {product.price}"
                    for product in all_products
                ]
            }
            
            await self.log(f"检索完成，找到 {len(all_products)} 个商品", log_callback)
            return result
        except Exception as e:
            await self.log(f"检索失败: {e}", log_callback)
            # 返回默认值
            return {
                "query": input_data,
                "total_products": 0,
                "products": [],
                "recommendations": []
            }
        finally:
            # 关闭HTTP会话
            await self._close_session()
