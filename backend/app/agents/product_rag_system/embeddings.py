"""
嵌入数据库模块 - 管理文本向量化和向量存储
"""
import openai
import chromadb
from chromadb.api.types import Documents, Embeddings, EmbeddingFunction
from app.config import settings


class CustomEmbeddingFunction(EmbeddingFunction[Documents]):
    """Custom embedding function using SiliconFlow API"""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model_name: str = settings.EMBEDING_MODEL,
    ):
        """
        Initialize SiliconFlow embedding function

        Args:
            api_key: SiliconFlow API key
            base_url: SiliconFlow API base URL
            model_name: Model name for embeddings
        """
        self.model_name = model_name
        self.client = openai.OpenAI(api_key=api_key, base_url=base_url)

    def __call__(self, input: Documents) -> Embeddings:
        """Generate embeddings for documents"""
        response = self.client.embeddings.create(model=self.model_name, input=input)
        return [item.embedding for item in response.data]

    @staticmethod
    def name() -> str:
        """Get embedding function name"""
        return "siliconflow_free_api"

    def get_model_name(self) -> str:
        """Get model name"""
        return self.model_name

class EmbeddingDatabase:
    """嵌入数据库类 - 管理向量存储"""
    
    def __init__(self, 
                 embedding_model: str = None, 
                 distance_type: str = "cosine",
                 db_path: str = "./chroma_taobao_v1"):
        
        self.embedding_model = embedding_model or settings.EMBEDING_MODEL
        self.distance_type = self._determine_distance_type(embedding_model)
        self.db_path = db_path
        
        self.embedding_fn = CustomEmbeddingFunction(
            api_key=settings.SILICONFLOW_API_KEY,
            base_url=settings.SILICONFLOW_BASE_URL,
            model_name=self.embedding_model
        )
        
        # 初始化ChromaDB客户端
        self.chroma_client = chromadb.PersistentClient(path=self.db_path)
        
        # 创建或获取集合
        self.collection = self.chroma_client.get_or_create_collection(
            name="taobao_products",
            embedding_function=self.embedding_fn,
            metadata={"hnsw:space": self.distance_type},
        )
    
    def _determine_distance_type(self, model_name: str) -> str:
        """根据模型名称确定距离度量方式"""
        if model_name:
            if "m3" in model_name.lower() or "zh" in model_name.lower():
                return "cosine"  # 余弦距离
        return "ip"  # 内积距离
    
    def index_documents(self, ids: list, documents: list, metadatas: list):
        """批量索引文档到向量库"""
        if self.collection.count() > 0:
            print(f"已有 {self.collection.count()} 条商品向量，跳过索引")
            return
        
        batch_size = 100
        for i in range(0, len(ids), batch_size):
            self.collection.add(
                ids=ids[i : i + batch_size],
                documents=documents[i : i + batch_size],
                metadatas=metadatas[i : i + batch_size],
            )
        print(f"成功索引 {len(ids)} 条商品向量")
    
    def query(self, query_text: str, top_k: int = 3) -> dict:
        """向量相似度查询"""
        results = self.collection.query(
            query_texts=[query_text],
            n_results=top_k,
            include=["metadatas", "distances"]
        )
        return results
    
    def get_collection_size(self) -> int:
        """获取集合中的文档数量"""
        return self.collection.count()
    
    def similarity_to_score(self, distance: float) -> float:
        """根据距离类型将距离转换为相似度分数"""
        if self.distance_type == "cosine":
            return 1 - distance
        else:  # ip
            return max(0, 1 - distance)