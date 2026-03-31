from typing import List, Dict, Any
from sqlalchemy import select, String, func
from app.dependencies import AsyncSessionLocal
from app.knowledge_base.models import EntityAlias
from app.knowledge_base.entity_vector_store import search_entity_candidates
import asyncio

async def lookup_aliases(mention: str, entity_type: str) -> List[Dict[str, Any]]:
    """Performs an exact and partial text match on the SQL entity aliases table."""
    results = []
    mention_lower = mention.lower()
    
    async with AsyncSessionLocal() as session:
        # Exact match
        stmt_exact = select(EntityAlias).where(
            EntityAlias.entity_type == entity_type,
            func.lower(EntityAlias.alias) == mention_lower
        )
        exact_res = await session.execute(stmt_exact)
        
        for alias in exact_res.scalars().all():
            results.append({
                "canonical_name": alias.canonical_name,
                "entity_type": alias.entity_type,
                "entity_id": alias.entity_id,
                "alias": alias.alias,
                "match_type": "exact",
                "score": 1.0 # Highest relevance for exact matches
            })
            
        # Partial match
        # Limit partial matches to avoid noise
        stmt_partial = select(EntityAlias).where(
            EntityAlias.entity_type == entity_type,
            func.lower(EntityAlias.alias).like(f"%{mention_lower}%"),
            func.lower(EntityAlias.alias) != mention_lower # exclude exact
        ).limit(10)
        
        partial_res = await session.execute(stmt_partial)
        
        for alias in partial_res.scalars().all():
            results.append({
                "canonical_name": alias.canonical_name,
                "entity_type": alias.entity_type,
                "entity_id": alias.entity_id,
                "alias": alias.alias,
                "match_type": "partial",
                "score": 0.8
            })
            
    return results

async def vector_search_entities(mention: str, entity_type: str, k: int = 10) -> List[Dict[str, Any]]:
    """Performs semantic search using vector store."""
    def _run_search():
        return search_entity_candidates(mention, entity_type, k)
        
    try:
         return await asyncio.to_thread(_run_search)
    except Exception as e:
         print(f"Error in vector search: {e}")
         return []

def merge_candidates(alias_results: List[Dict[str, Any]], vector_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Merge and deduplicate results by canonical_name, preferring alias results (higher score)."""
    merged = {}
    
    # Process alias results first
    for res in alias_results:
        c_name = res["canonical_name"]
        if c_name not in merged:
            merged[c_name] = res
            
    # Process vector results, only adding if not already present or if we need to update score (unlikely)
    for res in vector_results:
        c_name = res["canonical_name"]
        if c_name not in merged:
            # Vector similarity scores are distance based usually, but here Langchain gives a float.
            # Assuming score is 0.0-1.0 relevance. If it's L1/L2 distance, we'd invert it.
            # search_entity_candidates returns distance. Let's normalize it to a pseudo score where lower distance -> higher score
            distance = res.get("score", 1.0)
            pseudo_score = max(0.0, 1.0 - (distance / 2.0)) # Rough heuristic for L2
            
            res_copied = dict(res)
            res_copied["match_type"] = "semantic"
            res_copied["score"] = pseudo_score
            merged[c_name] = res_copied
            
    # Sort merged list by score descending
    final_list = list(merged.values())
    final_list.sort(key=lambda x: x.get("score", 0), reverse=True)
    
    return final_list
