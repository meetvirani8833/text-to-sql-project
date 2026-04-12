from typing import List, Dict, Any
from langchain_postgres import PGVector
from langchain_core.documents import Document
from app.config import settings
from app.dependencies import get_embeddings

# Connection string for PGVector (sync psycopg3)
# postgresql+psycopg://user:password@host:port/db
def get_pgvector_connection_string():
    base = (
        f"postgresql+psycopg://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@"
        f"{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
    )
    if settings.POSTGRES_SSLMODE:
        return f"{base}?sslmode={settings.POSTGRES_SSLMODE}"
    return base

# Engine args to survive Neon free-tier auto-suspend (kills connections after ~300s idle)
_ENGINE_ARGS = {
    "pool_pre_ping": True,     # test connection liveness before each use
    "pool_recycle": 270,       # recycle connections before Neon's 300s idle timeout
    "pool_size": 2,
    "max_overflow": 3,
}

# Singleton: reuse the same PGVector store to avoid repeated SSL connections to Neon
_table_vector_store = None

def get_vector_store():
    global _table_vector_store
    if _table_vector_store is None:
        _table_vector_store = PGVector(
            embeddings=get_embeddings(),
            collection_name="curriculum_tables",
            connection=get_pgvector_connection_string(),
            use_jsonb=True,
            engine_args=_ENGINE_ARGS,
        )
    return _table_vector_store

def _reset_vector_store():
    """Invalidate singleton so next call rebuilds the connection."""
    global _table_vector_store
    _table_vector_store = None

def upsert_table_embedding(table_name: str, explanation_text: str):
    """
    Upserts a document for the table into the vector store.
    Deletes any existing embedding for this table first to prevent duplicates.
    """
    store = get_vector_store()

    # Delete existing documents for this table to prevent duplicates
    try:
        store.delete(filter={"table_name": table_name})
    except Exception:
        # Some PGVector versions may not support filter-based delete;
        # in that case, we just add (minor duplication risk)
        pass

    doc = Document(
        page_content=f"{table_name}: {explanation_text}",
        metadata={"table_name": table_name}
    )
    store.add_documents([doc])

def search_tables(query: str, k: int = 10) -> List[Dict[str, Any]]:
    """
    Searches for tables semantically similar to the query.
    Retries once on connection errors (Neon AdminShutdown).
    """
    for attempt in range(2):
        try:
            store = get_vector_store()
            results = store.similarity_search_with_score(query, k=k)

            output = []
            for doc, score in results:
                output.append({
                    "table_name": doc.metadata.get("table_name"),
                    "explanation": doc.page_content,
                    "score": score
                })
            return output
        except Exception as e:
            if attempt == 0 and "AdminShutdown" in str(e):
                print(f"  Neon connection was suspended, reconnecting... ({e})")
                _reset_vector_store()
                continue
            raise
    return []

