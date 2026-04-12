from typing import List, Dict, Any, Optional
from langchain_postgres import PGVector
from langchain_core.documents import Document
from app.knowledge_base.vector_store import get_pgvector_connection_string, _ENGINE_ARGS
from app.dependencies import get_embeddings

# Singleton: reuse the same entity vector store across all calls
_entity_vector_store = None

def get_entity_vector_store():
    global _entity_vector_store
    if _entity_vector_store is None:
        _entity_vector_store = PGVector(
            embeddings=get_embeddings(),
            collection_name="entity_vectors",
            connection=get_pgvector_connection_string(),
            use_jsonb=True,
            engine_args=_ENGINE_ARGS,
        )
    return _entity_vector_store

def _reset_entity_vector_store():
    """Invalidate singleton so next call rebuilds the connection."""
    global _entity_vector_store
    _entity_vector_store = None

def upsert_entity_embeddings(documents: List[Document]):
    store = get_entity_vector_store()
    if documents:
        store.add_documents(documents)

def search_entity_candidates(query: str, entity_type: Optional[str] = None, k: int = 10) -> List[Dict[str, Any]]:
    filter_dict = {}
    if entity_type:
        filter_dict["entity_type"] = entity_type

    for attempt in range(2):
        try:
            store = get_entity_vector_store()
            results = store.similarity_search_with_score(query, k=k, filter=filter_dict if filter_dict else None)

            output = []
            for doc, score in results:
                output.append({
                    "canonical_name": doc.metadata.get("canonical_name"),
                    "entity_type": doc.metadata.get("entity_type"),
                    "entity_id": doc.metadata.get("entity_id"),
                    "alias": doc.metadata.get("alias"),
                    "score": score
                })
            return output
        except Exception as e:
            if attempt == 0 and "AdminShutdown" in str(e):
                print(f"  Neon entity connection was suspended, reconnecting... ({e})")
                _reset_entity_vector_store()
                continue
            raise
    return []

def clear_entity_embeddings(entity_type: Optional[str] = None):
    store = get_entity_vector_store()
    try:
        if entity_type:
            store.delete(filter={"entity_type": entity_type})
        else:
            store.delete(filter={})
    except Exception:
        pass

