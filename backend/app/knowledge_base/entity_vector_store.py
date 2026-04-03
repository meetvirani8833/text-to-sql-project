from typing import List, Dict, Any, Optional
from langchain_postgres import PGVector
from langchain_core.documents import Document
from app.knowledge_base.vector_store import get_pgvector_connection_string
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
        )
    return _entity_vector_store

def upsert_entity_embeddings(documents: List[Document]):
    store = get_entity_vector_store()
    if documents:
        store.add_documents(documents)

def search_entity_candidates(query: str, entity_type: Optional[str] = None, k: int = 10) -> List[Dict[str, Any]]:
    store = get_entity_vector_store()
    
    filter_dict = {}
    if entity_type:
        filter_dict["entity_type"] = entity_type
        
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

def clear_entity_embeddings(entity_type: Optional[str] = None):
    store = get_entity_vector_store()
    try:
        if entity_type:
            store.delete(filter={"entity_type": entity_type})
        else:
            # Emulating the try/catch behavior from vector_store.py if the store
            # doesn't support generic batch delete
            # Some PGVector implementations might not act correctly with empty filter drop
            store.delete(filter={})
    except Exception:
        pass
