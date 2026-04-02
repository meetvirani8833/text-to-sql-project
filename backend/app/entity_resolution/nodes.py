import json
from typing import Dict, Any, List
from langgraph.types import interrupt

from app.entity_resolution.state import EntityResolutionState
from app.entity_resolution.prompts import (
    DETECT_ENTITIES_PROMPT, RESOLVE_ENTITY_TYPE_PROMPT, 
    RERANK_CANDIDATES_PROMPT, REWRITE_WITH_ENTITIES_PROMPT
)
from app.knowledge_base.entity_config import load_entity_config
from app.entity_resolution.utils import lookup_aliases, vector_search_entities, merge_candidates
from app.dependencies import get_llm, get_llm_4o, get_llm_o4_mini, get_llm_gpt_5, get_llm_gpt_5_mini, get_llm_gpt_5_nano

async def detect_entities(state: EntityResolutionState) -> Dict[str, Any]:
    print("--- Detect Entities ---")
    
    config_map = load_entity_config()
    
    # Build nice text format of available entity types
    types_text = []
    for k, v in config_map.items():
        types_text.append(f"- {k}: {v.description if hasattr(v, 'description') and v.description else 'Target entity in ' + v.table}")
    
    # Build column context text from table_metadata and pruned_columns
    # This gives the LLM knowledge of what columns exist so it can
    # distinguish filters (column values/flags) from entities (needing KB resolution)
    column_context_lines = []
    table_metadata = state.get("table_metadata", [])
    pruned_columns = state.get("pruned_columns", {})
    
    # Group metadata by table, filtered to pruned columns
    tables_cols = {}
    for m in table_metadata:
        t = m["table_name"]
        col = m["column_name"]
        # Only show columns that were pruned (relevant to this query)
        allowed = pruned_columns.get(t)
        if allowed is not None and col not in allowed:
            continue
        if t not in tables_cols:
            tables_cols[t] = []
        desc = m.get("user_description") or m.get("generated_explanation") or ""
        # Truncate long descriptions to keep prompt compact
        if len(desc) > 150:
            desc = desc[:147] + "..."
        tables_cols[t].append(f"  - {col} ({m['data_type']}): {desc}")
    
    for t, cols in tables_cols.items():
        column_context_lines.append(f"Table: {t}")
        column_context_lines.extend(cols)
        column_context_lines.append("")
    
    column_context_text = "\n".join(column_context_lines) if column_context_lines else "No column context available."
    
    # Use pre-fetched kb hints text from state (which was fired in parallel earlier)
    kb_hints_text = state.get("kb_hints_text", "No KB hints available.")

    # Step 2: Detect entities using the extracted candidate phrases and KB hints
    prompt_input = {
        "rewritten_question": state["rewritten_question"],
        "entity_types_text": "\n".join(types_text),
        "column_context_text": column_context_text,
        "kb_hints_text": kb_hints_text
    }
    
    llm = get_llm_gpt_5()
    chain = DETECT_ENTITIES_PROMPT | llm
    res = await chain.ainvoke(prompt_input)
    content = res.content.strip()
    
    # Clean json block
    if content.startswith("```json"): content = content[7:]
    elif content.startswith("```"): content = content[3:]
    if content.endswith("```"): content = content[:-3]
    
    try:
        detected = json.loads(content.strip())
        if not isinstance(detected, list):
            detected = []
    except Exception as e:
        print(f"Entities JSON parse error: {e}")
        detected = []
        
    if not detected:
        print("  No entities detected (all mentions are filters or not entity-typed).")
        return {
            "detected_entities": [],
            "processing_index": 0,
            "resolved_entities": [],
            "entity_type_resolution": {},
            "resolution_complete": True
            # Keep rewritten_question unchanged - it was already set by the rewrite_question node
        }
        
    print(f"  Detected {len(detected)} entities.")
    
    # Initialize state with detected entities
    new_state = {
        "detected_entities": detected,
        "processing_index": 0,
        "resolved_entities": [],
        "entity_type_resolution": {},
        "resolution_complete": False
    }
    
    return new_state

async def resolve_entity_type(state: EntityResolutionState) -> Dict[str, Any]:
    print("--- Resolve Entity Type ---")
    idx = state.get("processing_index", 0)
    entities = state.get("detected_entities", [])
    cached_resolved = state.get("resolved_entities", [])
    
    if idx >= len(entities):
        return {} # Should not happen if routing is correct
    
    current_entity = entities[idx]
    mention = current_entity.get("text", "")
    
    # Check if this entity is already resolved from cache
    already_resolved = next(
        (e for e in cached_resolved if e.get("mention", "").lower() == mention.lower()),
        None
    )
    mention = entities[idx].get("text", "")
    candidates = entities[idx].get("candidate_types", [])
    
    print(f"  Processing [{idx+1}/{len(entities)}]: '{mention}'")
    print(f"  Candidate types: {candidates}")
    
    # Auto-resolve if only one type
    if len(candidates) == 1:
        resolved_type = candidates[0]
        print(f"  Auto-resolved type (only 1 candidate): {resolved_type}")
        return {"entity_type_resolution": {mention: resolved_type}}
        
    # If NO candidates for some reason, we shouldn't fail fatally, just skip it.
    if not candidates:
        print(f"  No candidates found for '{mention}', skipping to random type.")
        types_keys = list(load_entity_config().keys())
        return {"entity_type_resolution": {mention: types_keys[0] if types_keys else "unknown"}}
    
    # **FIX #1: Ambiguity Detection**
    # If multiple candidates (e.g., "commerce" → department/course/programme), 
    # ask user for type clarification
    if len(candidates) > 1:
        print(f"  [AMBIGUITY] Mention '{mention}' has {len(candidates)} possible types")
        print(f"  Requesting type clarification from user")
        return {
            "clarification_type": "type",
            "clarification_entity": mention,
            "clarification_options": candidates
        }
        
    # Multiple candidates -> LLM resolution
    llm = get_llm_gpt_5_mini()
    chain = RESOLVE_ENTITY_TYPE_PROMPT | llm
    res = await chain.ainvoke({
        "rewritten_question": state["rewritten_question"],
        "mention": mention,
        "candidate_types": str(candidates)
    })
    
    content = res.content.strip()
    if content.startswith("```json"): content = content[7:]
    elif content.startswith("```"): content = content[3:]
    if content.endswith("```"): content = content[:-3]
    
    try:
        decision = json.loads(content.strip())
        resolved_type = decision.get("resolved_type", candidates[0])
        confidence = decision.get("confidence", "low")
        
        # Verify resolved_type is in candidates just in case hallucination
        if resolved_type not in candidates:
            resolved_type = candidates[0]
            confidence = "low"
            
        print(f"  LLM guessed type: {resolved_type} (confidence: {confidence})")
        
        if confidence.lower() == "high":
            return {"entity_type_resolution": {mention: resolved_type}}
        else:
            # Low confidence -> Need clarification
            print(f"  [AMBIGUITY] Low confidence for '{mention}'. Requesting type clarification.")
            return {
                "clarification_type": "type",
                "clarification_entity": mention,
                "clarification_options": candidates
            }
            
    except Exception as e:
        print(f"Resolve Type JSON parse error: {e}")
        # Default to first if failed
        return {"entity_type_resolution": {mention: candidates[0]}}

async def retrieve_candidates(state: EntityResolutionState) -> Dict[str, Any]:
    print("--- Retrieve Candidates ---")
    idx = state["processing_index"]
    mention = state["detected_entities"][idx]["text"]
    
    resolutions = state.get("entity_type_resolution", {})
    entity_type = resolutions.get(mention)
    
    if not entity_type:
        print(f"  Error: No resolved type for '{mention}'")
        return {"entity_candidates": {mention: []}}
        
    print(f"  Fetching DB/Vector candidates for '{mention}' ({entity_type})")
    alias_res = await lookup_aliases(mention, entity_type)
    vector_res = await vector_search_entities(mention, entity_type, k=5)
    
    merged = merge_candidates(alias_res, vector_res)
    print(f"  Found {len(merged)} potential matches.")
    
    # Store currently active candidates
    return {"entity_candidates": {mention: merged}}

async def rank_candidates(state: EntityResolutionState) -> Dict[str, Any]:
    print("--- Rank Candidates ---")
    idx = state["processing_index"]
    mention = state["detected_entities"][idx]["text"]
    
    resolutions = state.get("entity_type_resolution", {})
    entity_type = resolutions.get(mention)
    
    candidates = state.get("entity_candidates", {}).get(mention, [])
    
    if not candidates:
        print(f"  No candidates found! Auto-skipping '{mention}'.")
        return {
            "processing_index": idx + 1,
            "clarification_type": None,
            "clarification_entity": None,
            "clarification_options": None
        }
        
    # Check for exact matches
    exact_matches = [c for c in candidates if c.get("match_type") == "exact"]
    if len(exact_matches) == 1:
        print(f"  Auto-resolved value (Exact Match): {exact_matches[0]['canonical_name']}")
        resolved_entity = {"mention": mention, "entity_type": entity_type, 
                          "canonical_name": exact_matches[0]["canonical_name"], 
                          "entity_id": exact_matches[0]["entity_id"]}
        
        new_resolved = state.get("resolved_entities", []) + [resolved_entity]
        
        return {
            "resolved_entities": new_resolved,
            "processing_index": idx + 1,
            "clarification_type": None,
            "clarification_entity": None,
            "clarification_options": None
        }
    elif len(candidates) == 1:
        # Only one candidate available, trust it
        print(f"  Auto-resolved value (Only 1 candidate): {candidates[0]['canonical_name']}")
        resolved_entity = {"mention": mention, "entity_type": entity_type, 
                          "canonical_name": candidates[0]["canonical_name"], 
                          "entity_id": candidates[0]["entity_id"]}
        
        new_resolved = state.get("resolved_entities", []) + [resolved_entity]

        
        return {
            "resolved_entities": new_resolved,
            "processing_index": idx + 1,
            "clarification_type": None,
            "clarification_entity": None,
            "clarification_options": None
        }
        
    # Call LLM for ranking/ambiguity check
    print(f"  Ranking {len(candidates)} candidates via LLM...")
    llm = get_llm_gpt_5_mini()
    chain = RERANK_CANDIDATES_PROMPT | llm
    
    # Limit to top 10 for prompt size
    c_json = json.dumps([{k:v for k,v in c.items() if k in ['canonical_name','alias','score']} for c in candidates[:10]], indent=2)
    
    res = await chain.ainvoke({
        "rewritten_question": state["rewritten_question"],
        "mention": mention,
        "entity_type": entity_type,
        "candidates_json": c_json
    })
    
    content = res.content.strip()
    if content.startswith("```json"): content = content[7:]
    elif content.startswith("```"): content = content[3:]
    if content.endswith("```"): content = content[:-3]
    
    try:
        rank_decision = json.loads(content.strip())
        auto_resolve = rank_decision.get("auto_resolve", False)
        ranked = rank_decision.get("ranked", [])
        
        if auto_resolve and ranked:
            print(f"  LLM auto-resolved value: {ranked[0]['canonical_name']}")
            # Find the full object from our candidate list based on canonical_name
            best_c_name = ranked[0]["canonical_name"]
            matched_obj = next((c for c in candidates if c["canonical_name"] == best_c_name), candidates[0])
            
            resolved_entity = {"mention": mention, "entity_type": entity_type, 
                              "canonical_name": matched_obj["canonical_name"], 
                              "entity_id": matched_obj["entity_id"]}
            
            new_resolved = state.get("resolved_entities", []) + [resolved_entity]
            
            return {
                "resolved_entities": new_resolved,
                "processing_index": idx + 1,
                "clarification_type": None,
                "clarification_entity": None,
                "clarification_options": None
            }
        else:
            # Ambiguous -> clarification needed
            options = [c["canonical_name"] for c in candidates[:4]] # Limit options
            print(f"  Value ambiguous. Requesting clarification.")
            return {
                "clarification_type": "value",
                "clarification_entity": mention,
                "clarification_options": options
            }
            
    except Exception as e:
        print(f"  JSON Rerank error {e}. Requesting clarification anyway.")
        options = [c["canonical_name"] for c in candidates[:4]]
        return {
            "clarification_type": "value",
            "clarification_entity": mention,
            "clarification_options": options
        }

def handle_clarification(state: EntityResolutionState) -> Dict[str, Any]:
    print(f"--- Handle Clarification ({state.get('clarification_type')}) ---")
    
    # This calls the langgraph interrupt to pause execution.
    # The response should be a dictionary containing the user's selected choice or new specific values.
    # Example user response: {"selection_index": 0} OR {"question_change": "new user query"}
    
    user_response = interrupt({
        "type": state.get("clarification_type"),
        "entity": state.get("clarification_entity"),
        "options": state.get("clarification_options")
    })
    
    if "question_change" in user_response:
        return {"question_changed": True}
        
    selected_idx = user_response.get("selection_index", 0)
    options = state.get("clarification_options", [])
    
    # Safety bounds
    if selected_idx < 0 or selected_idx >= len(options):
        selected_idx = 0
        
    choice = options[selected_idx]
    mention = state.get("clarification_entity")
    c_type = state.get("clarification_type")
    
    idx = state["processing_index"]
    
    if c_type == "type":
        print(f"  User selected type: {choice}")
        return {"entity_type_resolution": {mention: choice}}
        # Do not increment processing_idx or clear options yet, edges will go to retrieve_candidates
        
    elif c_type == "value":
        print(f"  User selected value: {choice}")
        
        # We need the full canonical object to store in resolved_entities
        candidates = state.get("entity_candidates", {}).get(mention, [])
        matched_obj = next((c for c in candidates if c["canonical_name"] == choice), candidates[0])
        
        entity_type = state.get("entity_type_resolution", {}).get(mention)
        
        resolved_entity = {"mention": mention, "entity_type": entity_type, 
                          "canonical_name": matched_obj["canonical_name"], 
                          "entity_id": matched_obj["entity_id"]}
        
        new_resolved = state.get("resolved_entities", []) + [resolved_entity]

        
        return {
            "resolved_entities": new_resolved,
            "processing_index": idx + 1,
            "clarification_type": None,
            "clarification_entity": None,
            "clarification_options": None
        }
        
    return {}

def check_next_entity(state: EntityResolutionState) -> Dict[str, Any]:
    print("--- Check Next Entity ---")
    
    # Just a simple passthrough node to clear lingering clarification scope before looping back
    # The edges route according to processing_index
    idx = state.get("processing_index", 0)
    entities = state.get("detected_entities", [])
    
    print(f"  Resolved {idx}/{len(entities)} entities.")
    
    if idx >= len(entities):
        return {"resolution_complete": True}
    
    # Ensure processing_index is updated for next iteration (skip to next non-cached entity)
    return {}
        
    return {
        "clarification_type": None,
        "clarification_entity": None,
        "clarification_options": None
    }

async def rewrite_question_canonical(state: EntityResolutionState) -> Dict[str, Any]:
    print("--- Rewrite Question with Entities ---")
    
    # If no resolved entities, keep the existing rewritten_question
    # (which was already set by the rewrite_question node earlier in the pipeline)
    resolved = state.get("resolved_entities", [])
    if not resolved:
        print("  No entities resolved. Keeping existing rewritten question.")
        return {}  # Don't overwrite rewritten_question
        
    mapped_list = []
    for entity in resolved:
         mapped_list.append(f"- '{entity.get('mention')}' refers to {entity.get('entity_type')} '{entity.get('canonical_name')}'")
         
    llm = get_llm_gpt_5_nano()
    chain = REWRITE_WITH_ENTITIES_PROMPT | llm
    
    res = await chain.ainvoke({
        "rewritten_question": state["rewritten_question"],
        "resolved_entities_text": "\n".join(mapped_list)
    })
    
    rewritten = res.content.strip()
    # Strip unnecessary quotes if llm wraps the whole question in quotes
    if rewritten.startswith('"') and rewritten.endswith('"'): rewritten = rewritten[1:-1]
    
    print(f"  Original (Rewritten):  {state['rewritten_question']}")
    print(f"  Final Rewrite: {rewritten}")
    
    return {"rewritten_question": rewritten}
