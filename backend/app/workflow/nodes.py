import json
from decimal import Decimal
from datetime import date, datetime, time, timedelta
from typing import Dict, Any, List
from sqlalchemy import text, select
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from sqlalchemy.ext.asyncio import AsyncSession

from app.workflow.state import GraphState
from app.workflow.prompts import (
    REWRITE_QUESTION_PROMPT, FILTER_TABLES_PROMPT, PRUNE_COLUMNS_PROMPT,
    GENERATE_QUERY_PROMPT, VALIDATE_QUERY_PROMPT, SUMMARIZE_RESULT_PROMPT,
)
from app.knowledge_base.vector_store import search_tables
from app.knowledge_base.neo4j_graph import find_join_path
from app.knowledge_base.models import ColumnMeta, TableMeta
from app.dependencies import AsyncSessionLocal, get_llm, get_llm_4o, get_llm_o4_mini, get_llm_gpt_5, get_llm_gpt_5_mini, get_llm_gpt_5_nano
from app.utils.db import get_mysql_engine

# Helper to format dict list to string
def format_candidates(candidates: List[Dict[str, Any]]) -> str:
    return "\n".join([f"- {c.get('table_name')}: {c.get('explanation')}" for c in candidates])

def format_schema(metadata: List[Dict[str, Any]]) -> str:
    """Standard formatter for full table schemas.
    Adds bullet points and indents multi-line descriptions for better LLM readability."""
    tables = {}
    for m in metadata:
        t = m['table_name']
        if t not in tables:
            tables[t] = []
        
        desc = (m.get('user_description') or m.get('generated_explanation') or 'No description available').strip()
        # Indent multi-line descriptions for readability
        desc_formatted = '\n    '.join(desc.splitlines())
        tables[t].append(f"  - {m['column_name']} ({m['data_type']}):\n    {desc_formatted}")
        
    return "\n\n".join([f"Table: {t}\nColumns:\n" + "\n".join(cols) for t, cols in tables.items()])

def format_schema_for_generation(
    metadata: List[Dict[str, Any]],
    pruned_columns: Dict[str, List[str]],
    table_rules: Dict[str, List[str]] = None
) -> str:
    """Build an enriched schema string filtered to only the pruned columns.
    Includes full descriptions so the LLM understands enum values and business rules.
    Optionally injects per-table rules directly beneath each table's column list."""
    if table_rules is None:
        table_rules = {}
    tables = {}
    for m in metadata:
        t = m['table_name']
        col = m['column_name']
        # Only include columns selected by prune step
        allowed = pruned_columns.get(t)
        if allowed is not None and col not in allowed:
            continue
        if t not in tables:
            tables[t] = []
        desc = m.get('user_description') or ''
        # Indent multi-line descriptions for readability
        desc_formatted = '\n    '.join(desc.strip().splitlines())
        tables[t].append(f"  - {col} ({m['data_type']}):\n    {desc_formatted}")
    
    parts = []
    for t, cols in tables.items():
        section = f"Table: {t}\nColumns:\n" + "\n".join(cols)
        rules = table_rules.get(t, [])
        if rules:
            rules_text = "\n".join([f"  - {r}" for r in rules])
            section += f"\n\nRules for {t}:\n{rules_text}"
        parts.append(section)
    return "\n\n".join(parts)

# --- Nodes ---

async def rewrite_question(state: GraphState) -> Dict[str, Any]:
    print("--- Rewrite Question ---")
    question = state["user_question"]
    llm = get_llm_gpt_5_nano()
    chain = REWRITE_QUESTION_PROMPT | llm | StrOutputParser()
    rewritten = await chain.ainvoke({"user_question": question})
    return {"rewritten_question": rewritten}

async def extract_candidate_entities(state: GraphState) -> Dict[str, Any]:
    print("--- Extract Candidate Entities (Parallel) ---")
    from app.knowledge_base.entity_config import load_entity_config
    config_map = load_entity_config()
    
    # Step 1.1: Extract candidate phrases using a simple, unconstrained LLM prompt
    try:
        from app.entity_resolution.prompts import EXTRACT_CANDIDATE_PHRASES_PROMPT
        extract_llm = get_llm_gpt_5_nano()
        extract_chain = EXTRACT_CANDIDATE_PHRASES_PROMPT | extract_llm
        extract_res = await extract_chain.ainvoke({"question": state["rewritten_question"]})
        
        content = extract_res.content.strip()
        if content.startswith("```json"): content = content[7:]
        elif content.startswith("```"): content = content[3:]
        if content.endswith("```"): content = content[:-3]
        
        candidate_phrases = json.loads(content.strip())
        if not isinstance(candidate_phrases, list):
            candidate_phrases = []
    except Exception as e:
        print(f"  Warning: Failed to extract candidate phrases: {e}")
        candidate_phrases = []

    # Step 1.2: Vector search each extracted phrase and deduplicate
    kb_hints_text = "No relevant KB entries found."
    try:
        from app.knowledge_base.entity_vector_store import search_entity_candidates
        import asyncio
        
        all_hints = {}
        all_types = list(config_map.keys())
        for phrase in candidate_phrases:
            # Search each phrase against EVERY type individually to guarantee diversity (k=2)
            for e_type in all_types:
                results = await asyncio.to_thread(search_entity_candidates, phrase, e_type, 2)
                for r in results:
                    c_name = r.get("canonical_name")
                    score = r.get("score", 0.0) # PGVector returns distance (lower = better)
                    
                    # Keep the lowest distance match for each canonical name
                    if c_name not in all_hints or score < all_hints[c_name]["score"]:
                        all_hints[c_name] = r
                    
        if all_hints:
            # Sort all unique matches by distance ascending (lower distance = better) and take top 15 overall
            sorted_hints = sorted(all_hints.values(), key=lambda x: x.get("score", float("inf")))[:15]
            hints_lines = []
            for r in sorted_hints:
                # Convert distance to a pseudo-similarity (1 - distance) for the prompt
                similarity = max(0.0, 1.0 - r.get("score", 0.0))
                hints_lines.append(f'- "{r.get("canonical_name")}" ({r.get("entity_type")}, similarity: {similarity:.2f})')
            kb_hints_text = "\n".join(hints_lines)
            
        print(f"  Fetched KB hints for {len(candidate_phrases)} candidate phrases across {len(all_types)} types.")
    except Exception as e:
        print(f"  Warning: Failed to fetch KB hints: {e}")
        kb_hints_text = "No KB hints available."
        
    return {"kb_hints_text": kb_hints_text}

def retrieve_tables(state: GraphState) -> Dict[str, Any]:
    print("--- Retrieve Tables ---")
    question = state.get("rewritten_question", state["user_question"])
    # Vector store search is sync (pgvector sqlalchemy usually sync unless async driver used in custom way)
    # LangChain PGVector is sync by default.
    candidates = search_tables(question, k=10)
    return {"candidate_tables": candidates}

async def retrieve_high_level_metadata(state: GraphState) -> Dict[str, Any]:
    print("--- Retrieve High Level Metadata ---")
    
    candidates = state.get("candidate_tables", [])
    candidate_names = [c["table_name"] for c in candidates] if candidates else []

    rules = []
    table_rules: Dict[str, List[str]] = {}
    async with AsyncSessionLocal() as session:
        from app.knowledge_base.models import Rule, RuleScope
        # Fetch active rules: global (database scope) + table-specific for candidate tables
        stmt = (
            select(Rule)
            .where(Rule.is_active == True)
            .where(
                Rule.scope_identifier.in_(candidate_names)
                | (Rule.scope == RuleScope.DATABASE)
            )
        )
        result = await session.execute(stmt)
        for rule in result.scalars().all():
            if rule.scope == RuleScope.TABLE:
                # Bucket by table name for inline injection
                if rule.scope_identifier not in table_rules:
                    table_rules[rule.scope_identifier] = []
                table_rules[rule.scope_identifier].append(rule.rule_text)
            else:
                # Global/database rules go in the flat list
                rules.append(rule.rule_text)

    if rules:
        print(f"  Loaded {len(rules)} global rules.")
    for t, tr in table_rules.items():
        print(f"  Loaded {len(tr)} rules for table '{t}'.")

    return {"applicable_rules": rules, "table_rules": table_rules}

async def filter_tables(state: GraphState) -> Dict[str, Any]:
    print("--- Filter Tables ---")
    llm = get_llm_gpt_5_nano()
    candidates = state["candidate_tables"]
    candidates_text = format_candidates(candidates)
    
    applicable_rules = state.get("applicable_rules", [])
    table_rules = state.get("table_rules", {})
    
    rules_list = []
    if applicable_rules:
        rules_list.extend([f"- [Global] {r}" for r in applicable_rules])
    for table, r_list in table_rules.items():
        rules_list.extend([f"- [Table: {table}] {r}" for r in r_list])
    rules_text = "\n".join(rules_list) if rules_list else "None"
    
    chain = FILTER_TABLES_PROMPT | llm | JsonOutputParser()
    try:
        selected = await chain.ainvoke({
            "rewritten_question": state["rewritten_question"],
            "candidate_tables_text": candidates_text,
            "rules_text": rules_text
        })
        if isinstance(selected, dict) and "tables" in selected:
            selected = selected["tables"]
        elif isinstance(selected, dict):
            # Try to find list values
            for v in selected.values():
                if isinstance(v, list):
                    selected = v
                    break
    except Exception as e:
        print(f"Error filtering tables: {e}")
        # Fallback: take top 3
        selected = [c["table_name"] for c in candidates[:3]]
        
    if not isinstance(selected, list):
        selected = [c["table_name"] for c in candidates[:3]]

    # **CRITICAL FIX #4: Prioritize aca_batch as master table**
    # If aca_batch is in candidates but not selected, add it
    candidate_names = {c["table_name"] for c in candidates}
    if "aca_batch" in candidate_names and "aca_batch" not in selected:
        print("  [BATCH PRIORITY] Adding aca_batch table (master table)")
        selected = ["aca_batch"] + selected
    # If it's already selected, move it to the front (first priority)
    elif "aca_batch" in selected and selected[0] != "aca_batch":
        print("  [BATCH PRIORITY] Moving aca_batch to first position (master table)")
        selected.remove("aca_batch")
        selected = ["aca_batch"] + selected

    return {"selected_tables": selected}

async def retrieve_metadata(state: GraphState) -> Dict[str, Any]:
    print("--- Retrieve Metadata ---")
    selected = state["selected_tables"]
    metadata = []
    
    async with AsyncSessionLocal() as session:
        # Fetch columns for tables in `selected`
        stmt = (
            select(ColumnMeta, TableMeta.table_name)
            .join(TableMeta)
            .where(TableMeta.table_name.in_(selected))
        )
        result = await session.execute(stmt)
        for col, t_name in result:
             metadata.append({
                 "table_name": t_name,
                 "column_name": col.column_name,
                 "data_type": col.data_type,
                 "user_description": col.user_description,
                 "visualization_name": col.visualization_name,
                 "is_pk": col.is_primary_key,
                 "is_fk": col.is_foreign_key
             })
             
    return {"table_metadata": metadata}

#def retrieve_join_paths(state: GraphState) -> Dict[str, Any]:
#    print("--- Retrieve Join Paths ---")
#    selected = state["selected_tables"]
#    if len(selected) < 2:
#        return {"join_paths": []}
#    
#    # Simple path for pair, or just first two for MVP
#    paths = find_join_path(selected[0], selected[1])
#    return {"join_paths": paths}

def retrieve_join_paths(state: GraphState) -> Dict[str, Any]:
    print("--- Retrieve Join Paths ---")
    selected = state["selected_tables"]
    if len(selected) < 2:
        return {"join_paths": []}
    
    all_paths = []
    # Find join paths between consecutive pairs: A→B, B→C, C→D, etc.
    for i in range(len(selected) - 1):
        table_start = selected[i]
        table_end = selected[i + 1]
        print(f"  Finding join path: {table_start} → {table_end}")
        paths = find_join_path(table_start, table_end)
        if paths:
            all_paths.extend(paths)
        else:
            print(f"  Warning: No join path found between {table_start} and {table_end}")
    
    return {"join_paths": all_paths}

def retrieve_missing_tables(state: GraphState) -> Dict[str, Any]:
    print("--- Retrieve Missing Tables ---")
    current = set(state["selected_tables"])
    missing = set()
    
    # Logic to extract tables from join_paths step
    for step in state.get("join_paths", []):
        if step["start"] not in current: missing.add(step["start"])
        if step["end"] not in current: missing.add(step["end"])
    
    if not missing:
        return {}
    
    new_selected = list(current.union(missing))
    return {"selected_tables": new_selected}

async def prune_columns(state: GraphState) -> Dict[str, Any]:
    print("--- Prune Columns ---")
    
    # Fast path: skip LLM completely if requested
    config = state.get("pruning_config", {})
    if config.get("skip", False):
         print("  [DEBUG] Skipping prune_columns node (fast path requested).")
         return {"pruned_columns": {}, "table_metadata": state["table_metadata"]}

    question = state["rewritten_question"]
    metadata = state.get("table_metadata", [])
    join_paths = state.get("join_paths", [])
    applicable_rules = state.get("applicable_rules", [])
    table_rules = state.get("table_rules", {})
    
    schema_text = format_schema(metadata)
    join_paths_text = "\n".join([f"{p['start']} JOIN {p['end']} ON {p['start']}.{p['from_col']} = {p['end']}.{p['to_col']}" for p in join_paths]) if join_paths else "None"
    
    rules_list = []
    if applicable_rules:
        rules_list.extend([f"- [Global] {r}" for r in applicable_rules])
    for table, r_list in table_rules.items():
        rules_list.extend([f"- [Table: {table}] {r}" for r in r_list])
    rules_text = "\n".join(rules_list) if rules_list else "None"
    
    # Load entity columns to protect
    try:
        from app.knowledge_base.entity_config import load_entity_config
        entity_cfs = load_entity_config()
        entity_cols = set()
        for ec in entity_cfs.values():
            entity_cols.add(ec.name_column)
            if ec.alias_columns:
                for ac in ec.alias_columns:
                    entity_cols.add(ac)
        entity_columns_text = ", ".join(sorted(list(entity_cols)))
        if not entity_columns_text:
            entity_columns_text = "None"
    except Exception as e:
        print(f"  Warning: failed to load entity config: {e}")
        entity_columns_text = "None"

    # Use gpt-4o for better accuracy with large schemas (90+ columns)
    llm = get_llm_gpt_5()
    chain = PRUNE_COLUMNS_PROMPT | llm | JsonOutputParser()
    
    try:
        pruned = await chain.ainvoke({
            "rewritten_question": question,
            "table_schemas_text": schema_text,
            "join_paths_text": join_paths_text,
            "rules_text": rules_text,
            "entity_columns_text": entity_columns_text
        })
    except Exception as e:
        print(f"  Error parsing pruned columns: {e}. Defaulting to all columns.")
        pruned = {}
        for m in metadata:
            t = m["table_name"]
            if t not in pruned: pruned[t] = []
            pruned[t].append(m["column_name"])
            
    return {"pruned_columns": pruned}

async def verify_entity_coverage(state: GraphState) -> Dict[str, Any]:
    print("--- Verify Entity Coverage ---")
    llm = get_llm_gpt_5()
    
    try:
        from app.knowledge_base.entity_config import load_entity_config
        config_map = load_entity_config()
        types_text = []
        for k, v in config_map.items():
            types_text.append(f"- {k}: {v.description if hasattr(v, 'description') and v.description else 'Target entity in ' + v.table}")
        entity_types = "\n".join(types_text)
    except Exception:
        entity_types = "None"
        
    column_context_lines = []
    table_metadata = state.get("table_metadata", [])
    pruned_columns = state.get("pruned_columns", {})
    tables_cols = {}
    for m in table_metadata:
        t = m["table_name"]
        col = m["column_name"]
        allowed = pruned_columns.get(t)
        if allowed is not None and col not in allowed:
            continue
        if t not in tables_cols:
            tables_cols[t] = []
        desc = m.get("user_description") or m.get("generated_explanation") or ""
        if len(desc) > 150:
            desc = desc[:147] + "..."
        tables_cols[t].append(f"  - {col} ({m['data_type']}): {desc}")
    
    for t, cols in tables_cols.items():
        column_context_lines.append(f"Table: {t}")
        column_context_lines.extend(cols)
        column_context_lines.append("")
    
    column_context_text = "\n".join(column_context_lines) if column_context_lines else "No column context available."
    
    # Format what the detector originally found (detected_entities, not resolved)
    detected = state.get("detected_entities", [])
    if detected:
        resolved_text = json.dumps(detected, indent=2)
    else:
        resolved_text = "[] (no entities detected)"
        
    chain = VERIFY_ENTITY_COVERAGE_PROMPT | llm | JsonOutputParser()
    try:
        result = await chain.ainvoke({
            "user_question": state.get("user_question", ""),
            "resolved_entities_text": resolved_text,
            "entity_types_text": entity_types,
            "column_context_text": column_context_text
        })
        
        flags = list(state.get("confidence_flags", []))
        if result.get("verdict") == "incomplete":
            for m in result.get("missed_mentions", []):
                flags.append(f"WARNING - Possibly missed entity: '{m.get('text')}' (likely {m.get('likely_type')}). {m.get('reasoning', '')}")
            print(f"  [WARN] Entity issues found: {len(result.get('missed_mentions',[]))} missed")
            return {"confidence_flags": flags}
            
        print("  Entity coverage verified as complete.")
        return {}
    except Exception as e:
        print(f"  Verify entity coverage failed: {e}. Proceeding.")
        return {}

async def generate_query(state: GraphState) -> Dict[str, Any]:
    print("--- Generate Query ---")
    llm = get_llm_gpt_5()
    
    # Build enriched schema: full descriptions filtered to pruned columns
    # Inject per-table rules inline so the LLM sees them in context
    enriched_schema = format_schema_for_generation(
        state.get("table_metadata", []),
        state.get("pruned_columns", {}),
        table_rules=state.get("table_rules", {})
    )
    join_text = json.dumps(state.get("join_paths", []), indent=2)
    
    # Also include error_details from previous failed attempt so LLM can self-correct
    error_context = ""
    if state.get("error_details"):
        error_context = f"\n\nPrevious attempt was rejected with this error:\n{state['error_details']}\nPlease fix it."
    
    flags = state.get("confidence_flags", [])
    flags_text = "\n".join([f"- {f}" for f in flags]) if flags else "None"
    
    chain = GENERATE_QUERY_PROMPT | llm | StrOutputParser()
    sql = await chain.ainvoke({
        "rewritten_question": state.get("rewritten_question", ""),
        "error_context": error_context,
        "pruned_columns_text": enriched_schema,
        "join_paths_text": join_text,
        "rules_text": "\n".join([f"- {r}" for r in state.get("applicable_rules", [])]),
        "confidence_flags_text": flags_text
    })
    
    sql = sql.replace("```sql", "").replace("```", "").strip()
    return {"generated_sql": sql}

def validate_query(state: GraphState) -> Dict[str, Any]:
    print("--- Validate Query ---")
    sql = state.get("generated_sql", "")
    
    if not sql:
        return {"error_details": "No SQL was generated."}
    
    # Use MySQL EXPLAIN to validate the query - database knows if it's valid, LLM does not
    engine = get_mysql_engine()
    if not engine:
        # If no engine, skip validation and try to execute
        return {"error_details": None}
    
    try:
        with engine.connect() as conn:
            conn.execute(text(f"EXPLAIN {sql}"))
        return {"error_details": None}
    except Exception as e:
        error_msg = str(e)
        print(f"Query Validation Error: {error_msg}")
        
        # Build enriched schema context so LLM knows what columns actually exist
        enriched_schema = format_schema_for_generation(
            state.get("table_metadata", []),
            state.get("pruned_columns", {}),
            table_rules=state.get("table_rules", {})
        )
        
        detailed_error = (
            f"The following SQL query failed validation:\n"
            f"{sql}\n\n"
            f"MySQL Error: {error_msg}\n\n"
            f"Review the available schema to fix unknown columns or tables:\n"
            f"{enriched_schema}"
        )
        return {"error_details": detailed_error, "retry_count": state.get("retry_count", 0) + 1}

def _sanitize_value(val):
    """Convert DB-specific types to JSON-serializable Python types."""
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, (datetime, date)):
        return val.isoformat()
    if isinstance(val, time):
        return val.isoformat()
    if isinstance(val, timedelta):
        return str(val)
    if isinstance(val, bytes):
        return val.decode("utf-8", errors="replace")
    return val

def execute_query(state: GraphState) -> Dict[str, Any]:
    print("--- Execute Query ---")
    sql = state.get("generated_sql", "")
    
    # Use helper engine (sync)
    engine = get_mysql_engine()
    if not engine:
        return {"query_result": None, "error_details": "MySQL connection not configured", "retry_count": state.get("retry_count", 0) + 1}

    try:
        # Build mapping from raw column -> visualization name
        viz_map = {}
        for m in state.get("table_metadata", []):
            if m.get("visualization_name"):
                viz_map[m["column_name"].lower()] = m["visualization_name"]

        with engine.connect() as conn:
            result = conn.execute(text(sql))
            raw_keys = result.keys()
            
            # Map raw keys to visualization names where available
            display_keys = []
            for k in raw_keys:
                k_lower = k.lower()
                if k_lower in viz_map:
                    display_keys.append(viz_map[k_lower])
                else:
                    # Fallback for LLM-generated aliases (e.g. TOTAL_REVENUE -> Total Revenue)
                    beautified = k.replace('_', ' ').title().strip()
                    beautified = " ".join([word if word.lower() != 'id' else 'ID' for word in beautified.split()])
                    display_keys.append(beautified)
            
            rows = [
                {dk: _sanitize_value(v) for dk, v in zip(display_keys, row)}
                for row in result.fetchall()
            ]
        return {"query_result": rows, "error_details": None}
    except Exception as e:
        print(f"Query Execution Error: {e}")
        return {"query_result": None, "error_details": str(e), "retry_count": state.get("retry_count", 0) + 1}

async def summarize_result(state: GraphState) -> Dict[str, Any]:
    print("--- Summarize Result ---")
    llm = get_llm()
    res = state.get("query_result", [])
    preview = str(res[:50]) if res else "No results"
    
    chain = SUMMARIZE_RESULT_PROMPT | llm
    res_obj = await chain.ainvoke({
        "user_question": state["user_question"],
        "generated_sql": state["generated_sql"],
        "row_count": len(res) if res else 0,
        "result_preview": preview
    })
    
    content = res_obj.content.strip()
    if content.startswith("```json"): content = content[7:]
    elif content.startswith("```"): content = content[3:]
    if content.endswith("```"): content = content[:-3]
    
    try:
        parsed = json.loads(content.strip())
        summary = parsed.get("summary_text", "Done.")
        viz_config = parsed.get("visualization_config", None) if parsed.get("visualizable") else None
    except Exception as e:
        print(f"Failed to parse LLM JSON: {e}")
        summary = content
        viz_config = None
    
    return {"result_summary": summary, "visualization_config": viz_config}

def fallback(state: GraphState) -> Dict[str, Any]:
    print("--- Fallback ---")
    err = state.get("error_details", "Unknown error")
    return {"result_summary": f"I couldn't answer that. Error: {err}"}
