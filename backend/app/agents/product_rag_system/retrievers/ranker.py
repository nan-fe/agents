"""
重排模块 - 对检索结果进行重排序
"""
from typing import List, Dict


class Ranker:
    """重排器类"""
    
    def rank(self, query: str, results: List[Dict]) -> List[Dict]:
        """对检索结果进行重排序"""
        if not results:
            return []
        
        # 计算混合分数
        for item in results:
            semantic_score = item.get("similarity", 0)
            bm25_score = item.get("bm25_score", 0)
            
            # 归一化BM25分数
            if bm25_score > 0:
                bm25_score = min(1.0, bm25_score / 5.0)
            
            # 加权平均计算最终分数
            item["rank_score"] = semantic_score * 0.6 + bm25_score * 0.4
        
        # 按排序分数降序排列
        results.sort(key=lambda x: x.get("rank_score", 0), reverse=True)
        
        return results
    
    def get_top_k_results(self, results: List[Dict], top_k: int = 3) -> List[Dict]:
        """获取前k个结果"""
        return results[:top_k]
