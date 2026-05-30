import json
import os
from contextlib import contextmanager
from typing import Optional

import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY", "")


@contextmanager
def _db():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _embed(text: str) -> list[float]:
    from google import genai
    from google.genai import types as gtypes
    client = genai.Client(
        api_key=GEMINI_API_KEY,
        http_options=gtypes.HttpOptions(api_version="v1"),
    )
    result = client.models.embed_content(
        model="gemini-embedding-001",
        contents=text,
        config=gtypes.EmbedContentConfig(output_dimensionality=768),
    )
    return result.embeddings[0].values


def _vec_str(embedding: list[float]) -> str:
    return "[" + ",".join(str(x) for x in embedding) + "]"


def add_memory(memory_id: str, content: str, metadata: dict):
    if not DATABASE_URL or not GEMINI_API_KEY:
        return
    try:
        embedding = _embed(content)
        user_id = metadata.get("user_id", "default")
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO memory_embeddings (id, user_id, embedding, content, metadata)
                       VALUES (%s, %s, %s::vector, %s, %s)
                       ON CONFLICT (id) DO UPDATE SET
                           embedding=EXCLUDED.embedding, content=EXCLUDED.content,
                           metadata=EXCLUDED.metadata, user_id=EXCLUDED.user_id""",
                    (memory_id, user_id, _vec_str(embedding), content, json.dumps(metadata)),
                )
    except Exception as e:
        print(f"[pg_vectors] add_memory error: {e}")


def search_memories(query: str, n_results: int = 5, user_id: Optional[str] = None) -> list[dict]:
    if not DATABASE_URL or not GEMINI_API_KEY:
        return []
    try:
        embedding = _embed(query)
        vec = _vec_str(embedding)
        with _db() as conn:
            with conn.cursor() as cur:
                if user_id:
                    cur.execute(
                        """SELECT id, content, metadata,
                                  1 - (embedding <=> %s::vector) AS relevance
                           FROM memory_embeddings
                           WHERE user_id = %s
                           ORDER BY embedding <=> %s::vector
                           LIMIT %s""",
                        (vec, user_id, vec, n_results),
                    )
                else:
                    cur.execute(
                        """SELECT id, content, metadata,
                                  1 - (embedding <=> %s::vector) AS relevance
                           FROM memory_embeddings
                           ORDER BY embedding <=> %s::vector
                           LIMIT %s""",
                        (vec, vec, n_results),
                    )
                rows = cur.fetchall()
        return [
            {
                "id": r["id"],
                "content": r["content"],
                "metadata": r["metadata"] if isinstance(r["metadata"], dict) else json.loads(r["metadata"] or "{}"),
                "relevance": round(float(r["relevance"]), 3),
            }
            for r in rows
        ]
    except Exception as e:
        print(f"[pg_vectors] search error: {e}")
        return []


def delete_memory(memory_id: str):
    if not DATABASE_URL:
        return
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM memory_embeddings WHERE id = %s", (memory_id,))
    except Exception as e:
        print(f"[pg_vectors] delete error: {e}")
