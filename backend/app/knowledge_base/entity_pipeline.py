import asyncio
import json
from typing import List, Dict, Any, Optional
from sqlalchemy import text, delete
from sqlalchemy.future import select
from langchain_core.documents import Document
from app.utils.db import get_mysql_engine
from app.dependencies import AsyncSessionLocal, get_llm
from app.knowledge_base.entity_config import load_entity_config, EntityTypeConfig
from app.knowledge_base.models import EntityAlias
from app.knowledge_base.entity_vector_store import upsert_entity_embeddings, clear_entity_embeddings

async def extract_entities_from_db(entity_type: str, config: EntityTypeConfig) -> List[Dict[str, Any]]:
    """Extracts entity records from the source MySQL database."""
    engine = get_mysql_engine()
    if not engine:
        print("MySQL engine not configured. Cannot extract entities.")
        return []

    # Build select list with GROUP BY to ensure distinct names
    select_cols = f"{config.name_column}"
    
    if config.alias_columns:
        for alias_col in config.alias_columns:
            select_cols += f", MAX({alias_col}) AS {alias_col}"
            
    query = f"SELECT {select_cols} FROM {config.table}"
    if config.filter_condition:
        query += f" WHERE {config.filter_condition}"
        
    query += f" GROUP BY {config.name_column}"
        
    print(f"  Executing query: {query}")
    
    entities = []
    # Using sync engine in async context for simplicity as per requirement, but running in thread is better.
    # We will just run it directly as requested: "Via get_mysql_engine() (sync)"
    def _run_query():
        with engine.connect() as conn:
            result = conn.execute(text(query))
            return [dict(row._mapping) for row in result]
            
    # Run sync query in a thread to not block the event loop
    entities = await asyncio.to_thread(_run_query)
    print(f"  Extracted {len(entities)} records for {entity_type}.")
    return entities

async def generate_llm_aliases(entity_type: str, canonical_name: str, existing_aliases: List[str]) -> List[str]:
    """Generates additional aliases/synonyms using the LLM."""
    llm = get_llm()
    
    existing_str = ", ".join(existing_aliases) if existing_aliases else "None"
    
    prompt = f"""Generate common abbreviations, acronyms, short forms for this {entity_type}: '{canonical_name}'. 
Existing aliases: {existing_str}. 
Return exactly a JSON array of strings and nothing else. Do not use markdown blocks."""

    try:
        response = await llm.ainvoke(prompt)
        content = response.content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]
        
        aliases = json.loads(content.strip())
        if isinstance(aliases, list):
            # Clean up and deduplicate against existing
            new_aliases = []
            for a in aliases:
                a_clean = str(a).strip()
                if a_clean and a_clean.lower() not in [ea.lower() for ea in existing_aliases] and a_clean.lower() != canonical_name.lower():
                    new_aliases.append(a_clean)
            return new_aliases
        return []
    except Exception as e:
        print(f"    Failed to generate LLM aliases for '{canonical_name}': {e}")
        return []

async def store_aliases(entity_type: str, entities: List[Dict[str, Any]], config: EntityTypeConfig) -> None:
    """Stores the canonical names and aliases in the postgres entity_aliases table."""
    async with AsyncSessionLocal() as session:
        # Step 1: Clear existing aliases for this entity type
        print(f"  Clearing existing db aliases for {entity_type}...")
        stmt = delete(EntityAlias).where(EntityAlias.entity_type == entity_type)
        await session.execute(stmt)
        await session.commit()
        
        # Step 2: Prepare and Dispatch LLM generation calls
        print(f"  Preparing {len(entities)} entities for alias generation...")
        
        tasks: List[Any] = []
        task_data: List[Any] = [] # stores (canonical_name, extracted_aliases_to_insert)
        
        for i, row in enumerate(entities):
            canonical_name = str(row[config.name_column])
            
            # Skip empty names
            if not canonical_name or canonical_name.strip() == "":
                continue
                
            aliases_to_insert = []
            
            # 1. Insert Canonical name as an alias
            aliases_to_insert.append({
                "alias": canonical_name,
                "source": "extracted"
            })
            
            # 2. Extract existing DB alias columns
            existing_aliases = []
            if config.alias_columns:
                for col in config.alias_columns:
                    val = row.get(col)
                    if val and str(val).strip():
                        val_str = str(val).strip()
                        existing_aliases.append(val_str)
                        # Add if not duplicate of canonical
                        if val_str.lower() != canonical_name.lower():
                            aliases_to_insert.append({
                                "alias": val_str,
                                "source": "extracted"
                            })
                            
            task_data.append((canonical_name, aliases_to_insert))
            tasks.append(generate_llm_aliases(entity_type, canonical_name, existing_aliases))
            
        print(f"  Executing {len(tasks)} LLM tasks in parallel batches of 20...")
        llm_results = []
        batch_size = 50
        
        # We process LLM calls in chunks of 50 to balance speed and rate-limits
        for batch_start in range(0, len(tasks), batch_size):
            batch_tasks = tasks[batch_start:batch_start + batch_size]  # type: ignore[index]
            batch_outputs = await asyncio.gather(*batch_tasks, return_exceptions=True)
            llm_results.extend(batch_outputs)
            print(f"    Finished {min(batch_start + batch_size, len(tasks))}/{len(tasks)} tasks...")

        # Step 3: Insert everything into the DB
        print(f"  Filtering and inserting generated DB aliases...")
        total_aliases = 0
        for i, (canonical_name, base_aliases) in enumerate(task_data):
            
            aliases_to_insert = list(base_aliases)
            
            # Add Generated LLM
            llm_aliases = llm_results[i]
            if isinstance(llm_aliases, list):
                for llm_alias in llm_aliases:
                    aliases_to_insert.append({
                        "alias": llm_alias,
                        "source": "llm_generated"
                    })
                
            # 4. Filter duplicates (case insensitive) before inserting
            seen = set()
            unique_aliases = []
            for a in aliases_to_insert:
                a_lower = a["alias"].lower()
                if a_lower not in seen:
                    seen.add(a_lower)
                    unique_aliases.append(a)
                    
            # 5. Insert to DB
            for u_alias in unique_aliases:
                db_alias = EntityAlias(
                    entity_type=entity_type,
                    alias=u_alias["alias"],
                    canonical_name=canonical_name,
                    entity_id=None,
                    source=u_alias["source"]
                )
                session.add(db_alias)
                total_aliases += 1  # type: ignore[operator]
                
        await session.commit()
        print(f"  Stored a total of {total_aliases} aliases for {entity_type}.")

async def embed_entities(entity_type: str) -> None:
    """Fetches aliases from DB and embeds them into PGVector."""
    print(f"  Emptying pgvector embeddings for {entity_type}...")
    # Emulate Async run for vector store operations. PGVector sync operations in thread
    await asyncio.to_thread(clear_entity_embeddings, entity_type)
    
    print(f"  Fetching aliases to embed for {entity_type}...")
    async with AsyncSessionLocal() as session:
        stmt = select(EntityAlias).where(EntityAlias.entity_type == entity_type)
        result = await session.execute(stmt)
        aliases = result.scalars().all()
        
        print(f"  Embedding {len(aliases)} alias documents...")
        count = 0
        
        # Batching upserts to PGVector (OpenAI max is 2048 per batch, use 1000)

        batch_size = 1000
        current_batch = []
        
        for alias in aliases:
            doc = Document(
                page_content=f"{entity_type}: {alias.alias} -> {alias.canonical_name}",
                metadata={
                    "entity_type": entity_type,
                    "canonical_name": alias.canonical_name,
                    "entity_id": alias.entity_id,
                    "alias": alias.alias
                }
            )
            current_batch.append(doc)
            count += 1
             
            if len(current_batch) >= batch_size:
                await asyncio.sleep(0.5) # Yield to event loop to prevent network pool deadlocks
                await asyncio.to_thread(upsert_entity_embeddings, current_batch)
                print(f"    Embedded {count}/{len(aliases)} documents...")
                current_batch = []
                
        if current_batch:
            await asyncio.to_thread(upsert_entity_embeddings, current_batch)
            print(f"    Embedded {count}/{len(aliases)} documents...")
                 
    print(f"  Finished embedding {count} aliases for {entity_type}.")

async def process_single_entity_type(entity_type: str, config: EntityTypeConfig) -> None:
    print(f"\n{'='*50}")
    print(f"Processing Entity Type: {entity_type}")
    print(f"{'='*50}")
    
    # Step A
    entities = await extract_entities_from_db(entity_type, config)
    if not entities:
        print(f"Skipping {entity_type} due to no extraction results.")
        return
        
    # Step B & C
    await store_aliases(entity_type, entities, config)
    
    # Step D
    await embed_entities(entity_type)

async def build_entity_kb(target_entity_types: Optional[List[str]] = None, use_checkpoint: bool = False) -> None:
    """Main orchestration function for building the entity knowledge base."""
    from app.entity_pipeline_checkpoint import (
        save_checkpoint, mark_entity_complete, load_checkpoint
    )
    
    config_map = load_entity_config()
    
    types_to_process = target_entity_types if target_entity_types else list(config_map.keys())
    
    # Get checkpoint info if resuming
    completed_entities = []
    if use_checkpoint:
        checkpoint = load_checkpoint()
        if checkpoint:
            completed_entities = checkpoint.get('completed_entities', [])
            # Filter out already-completed entities
            types_to_process = [t for t in types_to_process if t not in completed_entities]
    
    total_entities = target_entity_types if target_entity_types else list(config_map.keys())
    
    print(f"Starting Entity KB Build for types: {types_to_process}")
    
    for e_type in types_to_process:
        if e_type not in config_map:
            print(f"Warning: Entity type '{e_type}' not found in configuration. Skipping.")
            continue
            
        await process_single_entity_type(e_type, config_map[e_type])
        
        # Save checkpoint after each entity type is completed
        if use_checkpoint:
            mark_entity_complete(e_type, completed_entities, total_entities)
        
    print("\nEntity KB Pipeline finished.")
