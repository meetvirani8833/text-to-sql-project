from typing import Literal
from app.workflow.state import GraphState

def route_on_safety(state: GraphState) -> Literal["proceed", "unsafe_question"]:
    # Placeholder safety check
    q = state["user_question"].lower()
    if "drop" in q or "delete" in q:
        return "unsafe_question"
    return "proceed"

def route_on_missing_tables(state: GraphState) -> Literal["prune_columns", "join_tables_are_missing"]:
    # If join_paths introduced tables not in selected_tables
    selected = set(state["selected_tables"])
    needed = set()
    for step in state.get("join_paths", []):
        needed.add(step["start"])
        needed.add(step["end"])
    
    if not needed.issubset(selected):
        return "join_tables_are_missing"
    return "prune_columns"

def route_on_validation(state: GraphState) -> Literal["execute_query", "regenerate_query", "unknown_error"]:
    if not state.get("error_details"):
        return "execute_query"
    retries = state.get("retry_count", 0)
    if retries < 3:
        return "regenerate_query" 
    return "unknown_error"

def route_on_execution(state: GraphState) -> Literal["end", "regenerate_query", "unknown_error"]:
    if state.get("query_result") is not None:
        return "end"
        
    retries = state.get("retry_count", 0)
    if retries < 2:
        return "regenerate_query"
    return "unknown_error"
