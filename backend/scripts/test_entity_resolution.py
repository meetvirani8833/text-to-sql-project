import argparse
import asyncio
import sys
from pathlib import Path

# Add backend dir to sys.path so 'app' imports work correctly
backend_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(backend_dir))

from langgraph.checkpoint.memory import MemorySaver
from app.entity_resolution.graph import compile_entity_resolution_subgraph
from langgraph.types import Command

async def test_subgraph(question: str):
    """Orchestrates a CLI test of the Entity Resolution Subgraph with clarification support."""
    print(f"\n=======================================================")
    print(f"Testing Query: '{question}'")
    print(f"=======================================================\n")
    
    memory = MemorySaver()
    app = compile_entity_resolution_subgraph(checkpointer=memory)
    
    thread_config = {"configurable": {"thread_id": "test_thread_1"}}
    
    # Provide mock table_metadata and pruned_columns to simulate
    # the context that would be available after prune_columns in the real pipeline
    input_state = {
        "user_question": question,
        "rewritten_question": question,
        "table_metadata": [
            # Mock some columns so the detection prompt has context
            {"table_name": "aca_batch", "column_name": "is_honours_programme", "data_type": "TINYINT(1)", "user_description": "Boolean flag: 1 if this is an honours programme, 0 otherwise"},
            {"table_name": "aca_batch", "column_name": "department_name", "data_type": "VARCHAR(255)", "user_description": "Name of the academic department"},
            {"table_name": "aca_batch", "column_name": "programme_name", "data_type": "VARCHAR(255)", "user_description": "Name of the academic programme"},
            {"table_name": "aca_batch", "column_name": "batch_year", "data_type": "INT", "user_description": "Year of the batch"},
            {"table_name": "aca_batch", "column_name": "record_status", "data_type": "CHAR(1)", "user_description": "Record status: 'A' for active, 'I' for inactive"},
        ],
        "pruned_columns": {
            "aca_batch": ["is_honours_programme", "department_name", "programme_name", "batch_year", "record_status"]
        }
    }
    
    try:
        # Run graph
        async for state_update in app.astream(input_state, thread_config, stream_mode="updates"):
            pass # We rely on node prints
            
        # Check if paused (interrupted)
        while app.get_state(thread_config).next:
            current_state = app.get_state(thread_config)
            details = current_state.tasks[0].interrupts[0].value
            
            c_type = details.get("type")
            c_entity = details.get("entity")
            opts = details.get("options", [])
            
            print(f"\n[INTERRUPT]: Clarification required for '{c_entity}' ({c_type})")
            for i, o in enumerate(opts):
                print(f"  [{i}] {o}")
                
            print("\nEnter the index number of the option you mean, or type a new question to abort:")
            user_input = input("> ").strip()
            
            if user_input.isdigit() and 0 <= int(user_input) < len(opts):
                resume_payload = {"selection_index": int(user_input)}
            else:
                print("Interpreting as a question change...")
                resume_payload = {"question_change": user_input}
                
            # Resume processing
            async for state_update in app.astream(Command(resume=resume_payload), thread_config, stream_mode="updates"):
                 pass
                 
        # Final result check
        final_state = app.get_state(thread_config).values
        if final_state.get("question_changed"):
             print(f"\n[ABORTED] User changed the question.")
        else:
             print(f"\n[FINAL OUTPUT]")
             print(f"Rewritten Question: {final_state.get('rewritten_question')}")
             
    except Exception as e:
        print(f"\n[ERROR] Graph Execution Failed: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test the Entity Resolution Subgraph")
    parser.add_argument("question", help="The simulated user question.")
    args = parser.parse_args()
    
    asyncio.run(test_subgraph(args.question))
