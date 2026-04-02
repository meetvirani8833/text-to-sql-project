from typing import TypedDict, List, Dict, Any, Optional

class EntityResolutionState(TypedDict):
    # Input/Output
    user_question: str
    rewritten_question: str
    
    # Column context - passed from the main graph after prune_columns
    table_metadata: List[Dict[str, Any]]         # full column-level schema
    pruned_columns: Dict[str, List[str]]         # table -> [column_names]
    
    # Entity Detection
    kb_hints_text: str                           # entity candidate hints from vector search
    detected_entities: List[Dict[str, Any]]
    # Each: {"text": "computer science", "candidate_types": ["department","course","programme"]}
    
    # Entity Type Resolution - accumulates as entities are resolved one-by-one
    entity_type_resolution: Dict[str, str]
    # {"AI masters": "programme", "CSE": "department"}
    
    # Candidate Retrieval - for the CURRENT entity being processed
    entity_candidates: Dict[str, List[Dict[str, Any]]]
    
    # Final Resolved Entities - grows as each entity is resolved
    resolved_entities: List[Dict[str, Any]]
    # [{"mention": "CSE", "entity_type": "department", "canonical_name": "Computer Science and Engineering", "entity_id": "5"}, ...]
    
    # Clarification Control - for the CURRENT clarification
    clarification_type: str          # "type" or "value"
    clarification_entity: str        # mention being clarified
    clarification_options: List[str] # options for user
    question_changed: bool           # flag if user changes question during clarification
    
    # Processing Control - THIS IS THE LOOP INDEX
    processing_index: int            # which entity in detected_entities is currently being processed
    resolution_complete: bool        # True when ALL entities are resolved

