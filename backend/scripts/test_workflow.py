import asyncio
import sys
import os

# Add backend to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.workflow.graph import compiled_graph

async def main():
    print("Initializing workflow test...")
    
    # Sample question
    question = "How many active unique Programme Educational Objectives (PEOs) are there for the Master of Science degrees?"
    print(f"Question: {question}")
    
    # Initial state - no non-serializable objects
    inputs = {
        "user_question": question,
        "retry_count": 0,
        "selected_tables": [],
        "candidate_tables": [],
        "table_metadata": [],
        "join_paths": [],
        "applicable_rules": [],
        "detected_entities": [],
        "resolved_entities": []
    }
    
    print("\n--- Running Graph ---")
    try:
        # Stream the graph execution
        async for output in compiled_graph.astream(inputs):
            for key, value in output.items():
                print(f"Finished Node: {key}")
                # Optional: print partial state updates
                if "generated_sql" in value:
                     print(f"SQL: {value['generated_sql']}")
                if "result_summary" in value:
                     print(f"Summary: {value['result_summary']}")
                if "error_details" in value and value["error_details"]:
                     print(f"Error: {value['error_details']}")
                     
    except Exception as e:
        print(f"Graph execution failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
