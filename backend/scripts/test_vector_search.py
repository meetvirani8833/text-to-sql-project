import sys
import os

# Add backend to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.knowledge_base.vector_store import search_tables

if __name__ == "__main__":
    query = "student batches and academic programs"
    print(f"Searching for: '{query}'...")
    try:
        results = search_tables(query)
        print(f"\nFound {len(results)} results:")
        for res in results:
            # Handle different return structures if legacy code changes
            # Current implementation returns dict with 'table_name', 'explanation', 'score'
            # Note: score in langchain PGVector might be distance (lower is better) or similarity (higher is better)
            # usually it's distance for PGVector by default unless configured otherwise.
            print(f"- {res.get('table_name')} (Score: {res.get('score')})")
            print(f"  Explanation: {res.get('explanation', '')[:150]}...")
            print("-" * 40)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"\nError: {e}")
