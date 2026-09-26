"""
RAG 素材库 —— 基于 Chroma 的本地向量存储。

功能：
  - save(): 把本次生成的素材存入向量库
  - search(): 用主题检索历史相关素材

数据持久化在 data/vectorstore/ 目录，重启不丢失。
"""

import os
import time
from pathlib import Path
from langchain_chroma import Chroma
from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2

# 向量库存储路径
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
PERSIST_DIR = os.path.join(DATA_DIR, "vectorstore")
EMBEDDING_CACHE_DIR = os.path.join(DATA_DIR, "embedding-model")

# 本地 ONNX 模型（all-MiniLM-L6-v2，约 80 MB）。远程 LLM 网关只负责生成，
# 向量化不再依赖一个网关未部署的 text-embedding-* 模型。
class _LocalEmbeddingAdapter:
    """Expose Chroma's local function through LangChain's embedding protocol."""

    def __init__(self) -> None:
        self._model = ONNXMiniLM_L6_V2()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[float(value) for value in vector] for vector in self._model(texts)]

    def embed_query(self, text: str) -> list[float]:
        return [float(value) for value in self._model([text])[0]]


_embeddings: _LocalEmbeddingAdapter | None = None


def _get_embeddings() -> _LocalEmbeddingAdapter:
    """延迟初始化本地 ONNX embedding，并把模型缓存放在持久化 data 卷。"""
    global _embeddings
    if _embeddings is None:
        os.makedirs(EMBEDDING_CACHE_DIR, exist_ok=True)
        ONNXMiniLM_L6_V2.DOWNLOAD_PATH = Path(EMBEDDING_CACHE_DIR)
        _embeddings = _LocalEmbeddingAdapter()
    return _embeddings


def _get_store() -> Chroma:
    """获取 Chroma 向量库实例。"""
    os.makedirs(PERSIST_DIR, exist_ok=True)
    return Chroma(
        collection_name="content_agent_materials",
        embedding_function=_get_embeddings(),
        persist_directory=PERSIST_DIR,
    )


def save(topic: str, context: str, platform: str, topic_id: int | None = None) -> None:
    """
    把本次素材存入向量库。
    每次存一条记录：content = 素材摘要，metadata 带主题/平台/时间/topic_id。
    """
    if not context.strip():
        return

    store = _get_store()
    metadata = {
        "topic": topic,
        "platform": platform,
        "timestamp": str(int(time.time())),
    }
    if topic_id is not None:
        metadata["topic_id"] = topic_id
    store.add_texts(texts=[context], metadatas=[metadata])
    print(f"  💾 素材已存入向量库（{len(context)}字）")


def delete_by_topic_id(topic_id: int) -> int:
    """按 topic_id 删除该主题下所有向量记录，返回删除条数。"""
    try:
        store = _get_store()
        results = store.get(where={"topic_id": topic_id})
        ids = results.get("ids", [])
        if ids:
            store.delete(ids=ids)
            print(f"  🗑️ 已从向量库删除 {len(ids)} 条素材（topic_id: {topic_id}）")
        return len(ids)
    except Exception as e:
        print(f"  ⚠️ 向量库删除失败：{e}")
        return 0


def delete_by_topic_id_and_platform(topic_id: int, platform: str) -> int:
    """按 topic_id + platform 删除向量记录，返回删除条数。"""
    try:
        store = _get_store()
        results = store.get(where={"$and": [{"topic_id": topic_id}, {"platform": platform}]})
        ids = results.get("ids", [])
        if ids:
            store.delete(ids=ids)
            print(f"  🗑️ 已从向量库删除 {len(ids)} 条素材（topic_id: {topic_id}, 平台: {platform}）")
        return len(ids)
    except Exception as e:
        print(f"  ⚠️ 向量库删除失败：{e}")
        return 0


def search_similar(topic: str, k: int = 3) -> list[str]:
    """
    用主题检索历史相关素材，返回最多 k 条。
    如果向量库为空或检索失败，返回空列表（不影响主流程）。
    """
    try:
        store = _get_store()
        results = store.similarity_search(topic, k=k)
        return [doc.page_content for doc in results]
    except Exception as e:
        print(f"  ⚠️ 向量库检索失败（不影响主流程）：{e}")
        return []
