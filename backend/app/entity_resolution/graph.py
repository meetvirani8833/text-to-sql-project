from langgraph.graph import StateGraph, END
from app.entity_resolution.state import EntityResolutionState
from app.entity_resolution.nodes import (
    detect_entities, resolve_entity_type, retrieve_candidates,
    rank_candidates, handle_clarification, check_next_entity,
    rewrite_question_canonical
)
from app.entity_resolution.edges import (
    route_after_detection, route_after_type_resolution,
    route_after_ranking, route_after_clarification,
    route_check_next_entity
)

def build_entity_resolution_subgraph() -> StateGraph:
    """Builds and returns the Entity Resolution Subgraph state map (uncompiled)."""
    graph = StateGraph(EntityResolutionState)
    
    # 1. Add Nodes
    graph.add_node("detect_entities", detect_entities)
    graph.add_node("resolve_entity_type", resolve_entity_type)
    graph.add_node("retrieve_candidates", retrieve_candidates)
    graph.add_node("rank_candidates", rank_candidates)
    graph.add_node("handle_clarification", handle_clarification)
    graph.add_node("check_next_entity", check_next_entity)
    graph.add_node("rewrite_question", rewrite_question_canonical)
    
    # 2. Add entry point
    graph.set_entry_point("detect_entities")
    
    # 3. Add Edges and Routing
    # From Detect -> Resolve or directly to Rewrite if no entities
    graph.add_conditional_edges(
        "detect_entities",
        route_after_detection,
        {
            "resolve_entity_type": "resolve_entity_type",
            "rewrite_question": "rewrite_question"
        }
    )
    
    # From Resolve Type -> Retrieve or Clarify
    graph.add_conditional_edges(
        "resolve_entity_type",
        route_after_type_resolution,
        {
            "retrieve_candidates": "retrieve_candidates",
            "handle_clarification": "handle_clarification"
        }
    )
    
    # From Retrieve -> Rank
    graph.add_edge("retrieve_candidates", "rank_candidates")
    
    # From Rank -> Check Next or Clarify
    graph.add_conditional_edges(
        "rank_candidates",
        route_after_ranking,
        {
            "check_next_entity": "check_next_entity",
            "handle_clarification": "handle_clarification"
        }
    )
    
    # From Clarify -> Retrieve (if type was clarified) or Check Next (if value was clarified) or Abort
    graph.add_conditional_edges(
        "handle_clarification",
        route_after_clarification,
        {
            "retrieve_candidates": "retrieve_candidates",
            "check_next_entity": "check_next_entity",
            "abort": END # Prematurely exit if user changed the question
        }
    )
    
    # From Check Next -> Back to Resolve Type (LOOP) or Rewrite (FINISH)
    graph.add_conditional_edges(
        "check_next_entity",
        route_check_next_entity,
        {
            "resolve_entity_type": "resolve_entity_type", 
            "rewrite_question": "rewrite_question"
        }
    )
    
    # From Rewrite -> Done
    graph.add_edge("rewrite_question", END)
    
    return graph

# Expose compiled instance
# We don't attach the checkpointer here; the checkpointer will be attached dynamically 
# in the main graph run so it shares the global threads properly.
def compile_entity_resolution_subgraph(checkpointer=None):
    return build_entity_resolution_subgraph().compile(checkpointer=checkpointer)
