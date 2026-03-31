from typing import Literal
from app.entity_resolution.state import EntityResolutionState

def route_after_detection(state: EntityResolutionState) -> Literal["resolve_entity_type", "rewrite_question"]:
    """Routes based on whether any entities were detected."""
    # No entities detected or resolution explicitly complete -> skip to rewrite
    if not state.get("detected_entities") or state.get("resolution_complete"):
        return "rewrite_question"
    
    # Otherwise, start resolving the first entity
    return "resolve_entity_type"

def route_after_type_resolution(state: EntityResolutionState) -> Literal["retrieve_candidates", "handle_clarification"]:
    """If type is ambiguous, ask clarification, else retrieve candidates."""
    if state.get("clarification_type") == "type":
        return "handle_clarification"
    return "retrieve_candidates"

def route_after_ranking(state: EntityResolutionState) -> Literal["check_next_entity", "handle_clarification"]:
    """If value is ambiguous, ask clarification, else move to next entity check."""
    if state.get("clarification_type") == "value":
        return "handle_clarification"
    return "check_next_entity"

def route_after_clarification(state: EntityResolutionState) -> Literal["retrieve_candidates", "check_next_entity", "abort"]:
    """Routes based on what type of clarification was just answered by the user."""
    if state.get("question_changed"):
        # Special abort path if the user changes the question entirely
        return "abort"
        
    if state.get("clarification_type") == "type":
        # Type was just clarified - we now know what to search for, proceed to fetch candidates
        return "retrieve_candidates"
        
    # Value was just clarified, which means this specific entity is completely resolved
    return "check_next_entity"

def route_check_next_entity(state: EntityResolutionState) -> Literal["resolve_entity_type", "rewrite_question"]:
    """The multi-entity loop logic. Loops back if more entities exist, else finishes."""
    idx = state.get("processing_index", 0)
    entities = state.get("detected_entities", [])
    
    if idx < len(entities):
        return "resolve_entity_type"
    
    # All entities have been processed
    return "rewrite_question"
