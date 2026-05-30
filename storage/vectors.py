import chromadb
from chromadb.utils import embedding_functions
from pathlib import Path

CHROMA_PATH = Path.home() / ".braindump" / "chroma"

_collection = None


def _get_collection():
    global _collection
    if _collection is None:
        CHROMA_PATH.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(CHROMA_PATH))
        ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        _collection = client.get_or_create_collection(
            name="braindump_memories",
            embedding_function=ef,
        )
    return _collection


def add_memory(memory_id: str, content: str, metadata: dict):
    col = _get_collection()
    str_metadata = {k: str(v) for k, v in metadata.items()}
    col.upsert(ids=[memory_id], documents=[content], metadatas=[str_metadata])


def search_memories(query: str, n_results: int = 5) -> list[dict]:
    col = _get_collection()
    count = col.count()
    if count == 0:
        return []
    results = col.query(
        query_texts=[query],
        n_results=min(n_results, count),
    )
    return [
        {
            "id": results["ids"][0][i],
            "content": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
            "relevance": round(1 - results["distances"][0][i], 3),
        }
        for i in range(len(results["ids"][0]))
    ]


def delete_memory(memory_id: str):
    col = _get_collection()
    try:
        col.delete(ids=[memory_id])
    except Exception:
        pass
