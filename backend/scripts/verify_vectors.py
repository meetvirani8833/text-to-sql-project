import sys
from pathlib import Path

# Add the backend dir to sys.path so we can import 'app'
backend_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(backend_dir))

from app.knowledge_base.entity_vector_store import search_entity_candidates

if __name__ == "__main__":
    results = search_entity_candidates('CS department', entity_type='department', k=5)
    for r in results: 
        print(r)
