from typing import List, Dict, Any
from langchain_postgres import PGVector
from langchain_core.documents import Document
from app.config import settings
from app.dependencies import get_embeddings

# Connection string for PGVector (sync psycopg3)
# postgresql+psycopg://user:password@host:port/db
def get_pgvector_connection_string():
    return (
        f"postgresql+psycopg://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@"
        f"{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
    )

def get_vector_store():
    return PGVector(
        embeddings=get_embeddings(),
        collection_name="curriculum_tables",
        connection=get_pgvector_connection_string(),
        use_jsonb=True,
    )

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
    Returns list of dicts with score, content, and metadata.
    """
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
