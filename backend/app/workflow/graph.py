from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, END
from app.workflow.state import GraphState
from app.workflow.nodes import (
    rewrite_question, retrieve_tables, retrieve_high_level_metadata,
    filter_tables, retrieve_metadata, retrieve_join_paths, retrieve_missing_tables,
    prune_columns, generate_query, extract_candidate_entities,
    validate_query, execute_query, summarize_result, fallback
)
from app.entity_resolution.graph import build_entity_resolution_subgraph
from app.workflow.edges import (
    route_on_safety, route_on_missing_tables,
    route_on_validation, route_on_execution
)

def build_graph():
    graph = StateGraph(GraphState)

    # Nodes
    graph.add_node("rewrite_question", rewrite_question)
    graph.add_node("retrieve_tables", retrieve_tables)
    graph.add_node("retrieve_high_level_metadata", retrieve_high_level_metadata)
    graph.add_node("filter_tables", filter_tables)
    graph.add_node("retrieve_metadata", retrieve_metadata)
    graph.add_node("retrieve_join_paths", retrieve_join_paths)
    graph.add_node("retrieve_missing_tables", retrieve_missing_tables)
    graph.add_node("retrieve_metadata_for_missing", retrieve_metadata)  # reuses same fn, different edge target
    graph.add_node("prune_columns", prune_columns)
    graph.add_node("extract_candidate_entities", extract_candidate_entities)

    # Entity Resolution Subgraph - runs after column pruning
    entity_subgraph = build_entity_resolution_subgraph().compile()
    graph.add_node("entity_resolution", entity_subgraph)

    graph.add_node("generate_query", generate_query)
    graph.add_node("validate_query", validate_query)
    graph.add_node("execute_query", execute_query)
    graph.add_node("summarize_result", summarize_result)
    graph.add_node("fallback", fallback)

    # Edges
    # Start
    graph.set_entry_point("rewrite_question")

    # Parallel routes after rewriting question
    graph.add_edge("rewrite_question", "retrieve_tables")
    graph.add_edge("rewrite_question", "extract_candidate_entities")
    graph.add_edge("retrieve_tables", "retrieve_high_level_metadata")
    graph.add_edge("retrieve_high_level_metadata", "filter_tables")
    graph.add_edge("filter_tables", "retrieve_metadata")
    graph.add_edge("retrieve_metadata", "retrieve_join_paths")
    
    graph.add_conditional_edges(
        "retrieve_join_paths",
        route_on_missing_tables,
        {
            "prune_columns": "prune_columns",
            "join_tables_are_missing": "retrieve_missing_tables"
        }
    )
    
    # After fetching missing tables, get their metadata then go straight to prune_columns
    graph.add_edge("retrieve_missing_tables", "retrieve_metadata_for_missing")
    graph.add_edge("retrieve_metadata_for_missing", "prune_columns")
    
    # After pruning columns AND extracting candidate entities, run entity resolution
    graph.add_edge(["prune_columns", "extract_candidate_entities"], "entity_resolution")
    graph.add_edge("entity_resolution", "generate_query")

    graph.add_edge("generate_query", "validate_query")
    
    graph.add_conditional_edges(
        "validate_query",
        route_on_validation,
        {
            "execute_query": "execute_query",
            "regenerate_query": "generate_query",
            "unknown_error": "fallback"
        }
    )
    
    graph.add_conditional_edges(
        "execute_query",
        route_on_execution,
        {
            "end": "summarize_result",
            "regenerate_query": "generate_query",
            "unknown_error": "fallback"
        }
    )
    
    graph.add_edge("summarize_result", END)
    graph.add_edge("fallback", END)

    return graph.compile(checkpointer=MemorySaver())

compiled_graph = build_graph()
