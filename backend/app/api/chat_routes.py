import uuid
import json
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from langgraph.types import Command
from app.workflow.graph import compiled_graph

router = APIRouter(prefix="/api", tags=["Chat"])

class ChatRequest(BaseModel):
    text: str
    history: List[Dict[str, Any]] = []
    conversation_id: Optional[str] = None
    project_id: str = "default"  # Optional, fallback to default

class ChatResponse(BaseModel):
    conversation_id: str
    status: str
    Agent_response: str
    markdown: Optional[str] = None
    spreadsheet_structure: Optional[str] = None
    query_result: Optional[List[Dict[str, Any]]] = None
    visualization_config: Optional[Dict[str, Any]] = None
    clarification_options: Optional[List[str]] = None
    history: List[Dict[str, Any]]

def convert_to_html_table(data_arr: List[Dict[str, Any]]) -> Optional[str]:
    """Converts a list of dicts to an HTML <table> string."""
    if not data_arr:
        return None
        
    columns = list(data_arr[0].keys())
    
    html = "<table class='data-table'>\n"
    # Header
    html += "  <thead>\n    <tr>\n"
    for col in columns:
        html += f"      <th>{col}</th>\n"
    html += "    </tr>\n  </thead>\n"
    
    # Body
    html += "  <tbody>\n"
    for row in data_arr:
        html += "    <tr>\n"
        for col in columns:
            val = row.get(col, "")
            # Ensure safe string conversion
            val_str = str(val) if val is not None else ""
            html += f"      <td>{val_str}</td>\n"
        html += "    </tr>\n"
    html += "  </tbody>\n"
    html += "</table>"
    
    return html

def parse_user_selection(text: str, options: List[str]) -> Optional[int]:
    """Parses user input to find the selected option index (0-based)."""
    text = text.strip()
    
    # Check if it's a direct number (1-based via the prompt displayed to user)
    try:
        val = int(text)
        if 1 <= val <= len(options):
            return val - 1
    except ValueError:
        pass
        
    # Check for direct string match
    text_lower = text.lower()
    for i, opt in enumerate(options):
        if str(opt).lower() == text_lower:
            return i
            
    # Fuzzy checking could be added here if needed
    return None

@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    conversation_id = req.conversation_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": conversation_id}}
    
    # Safety check
    dangerous = ["drop ", "delete ", "truncate ", "alter ", "update ", "insert "]
    if any(kw in req.text.lower() for kw in dangerous):
        return ChatResponse(
            conversation_id=conversation_id,
            status="error",
            Agent_response="Your question contains potentially dangerous keywords. Please rephrase without SQL commands.",
            history=req.history
        )

    state = compiled_graph.get_state(config)
    is_interrupted = len(state.tasks) > 0 and getattr(state.tasks[0], "interrupts", None)
    
    inputs_or_command = None
    
    if is_interrupted:
        interrupt_details = state.tasks[0].interrupts[0].value
        options = interrupt_details.get("options", [])

        # All current interrupts expect a selection index (entity resolution clarifications).
        selection_idx = parse_user_selection(req.text, options)
        if selection_idx is not None:
            inputs_or_command = Command(resume={"selection_index": selection_idx})
        else:
            return ChatResponse(
                conversation_id=conversation_id,
                status="error",
                Agent_response="I didn't understand your selection. Please reply with the number of your choice, or clear the conversation to ask a new question.",
                history=req.history
            )
    else:
        # Starting fresh (or follow-up question on same thread)
        inputs_or_command = {
            "project_id": req.project_id,
            "user_question": req.text,
            "retry_count": 0,
            "selected_tables": [],
            "candidate_tables": [],
            "table_metadata": [],
            "join_paths": [],
            "applicable_rules": [],
            "detected_entities": [],
            "resolved_entities": []
        }

    # Run the graph
    try:
        final_node_name = None
        current_interrupt = None
        
        # Async stream over the graph execution
        async for event in compiled_graph.astream(inputs_or_command, config=config, stream_mode="updates"):
            for node_name, state_update in event.items():
                if node_name == "__interrupt__":
                    current_interrupt = state_update[0].value
                final_node_name = node_name
                
        # Retrieve final state from checkpointer
        current_state = compiled_graph.get_state(config)
        final_state_vals = current_state.values
        
        # 1. Handle if graph paused on an interrupt
        if len(current_state.tasks) > 0 and current_state.tasks[0].interrupts:
            interrupt_details = current_state.tasks[0].interrupts[0].value
            options = interrupt_details.get("options", [])
            
            msg_header = interrupt_details.get("message")
            if not msg_header:
                interrupt_type = interrupt_details.get("type")
                entity = interrupt_details.get("entity")
                
                if interrupt_type == "type" and entity:
                    msg_header = f"I found multiple types for **'{entity}'**. What kind of entity is it?"
                elif interrupt_type == "value" and entity:
                    msg_header = f"I found multiple matches for **'{entity}'**. Which one did you mean?"
                else:
                    msg_header = "Please clarify:"
            
            # Formatting options for the user as list
            display_options = []
            for i, opt in enumerate(options):
                display_opt = str(opt)
                if interrupt_type == "type":
                    # Beautify raw entity types: 'segment_name' -> 'Segment Name'
                    display_opt = display_opt.replace('_', ' ').title()
                display_options.append(display_opt)
                
            agent_text = msg_header
            
            new_history = list(req.history)
            if not new_history:
                new_history.append({"summary": None})
            new_history.append({"user": req.text})
            new_history.append({"system": agent_text})
            
            return ChatResponse(
                conversation_id=conversation_id,
                status="awaiting_clarification",
                Agent_response=agent_text,
                clarification_options=display_options,
                history=new_history
            )

        # 2. Graph completed normally
        agent_text = final_state_vals.get("result_summary", "")
        err = final_state_vals.get("error_details")
        sql = final_state_vals.get("generated_sql")
        
        status = "completed"
        if err and final_state_vals.get("query_result") is None:
            agent_text = err
            status = "error"
            
        # Format markdown exactly as text for now, could be enhanced
        markdown = agent_text
        
        # Build spreadsheet
        html_table = None
        query_result = final_state_vals.get("query_result")
        if query_result is not None and isinstance(query_result, list):
            html_table = convert_to_html_table(query_result)
            
        new_history = list(req.history)
        if not new_history:
            new_history.append({"summary": None})
        new_history.append({"user": req.text})
        new_history.append({"system": agent_text})
        
        viz_config = final_state_vals.get("visualization_config")
        
        return ChatResponse(
            conversation_id=conversation_id,
            status=status,
            Agent_response=agent_text,
            markdown=markdown,
            spreadsheet_structure=html_table,
            generated_sql=sql,
            query_result=query_result if query_result is not None else [],
            visualization_config=viz_config,
            history=new_history
        )
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return ChatResponse(
            conversation_id=conversation_id,
            status="error",
            Agent_response=f"Sorry, I couldn't process your question: {str(e)}",
            history=req.history
        )
