import asyncio
import argparse
import sys
from pathlib import Path

# Add the backend dir to sys.path so we can import 'app'
backend_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(backend_dir))

from app.knowledge_base.entity_pipeline import build_entity_kb
from app.entity_pipeline_checkpoint import (
    load_checkpoint, get_remaining_entities, clear_checkpoint,
    print_checkpoint_status
)

def main():
    parser = argparse.ArgumentParser(description="Rebuild the Entity Knowledge Base (Aliases & PGVector)")
    parser.add_argument(
        "--entity-type",
        type=str,
        help="Specify a single entity type to rebuild (e.g. department, programme). If omitted, rebuilds all.",
        default=None
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from last checkpoint (skip already-completed entities)"
    )
    parser.add_argument(
        "--clear-checkpoint",
        action="store_true",
        help="Clear checkpoint and rebuild all entities from scratch"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show current checkpoint status"
    )
    
    args = parser.parse_args()
    
    # Show checkpoint status if requested
    if args.status:
        print_checkpoint_status()
        return
    
    # Clear checkpoint if requested
    if args.clear_checkpoint:
        clear_checkpoint()
        print("Checkpoint cleared - will rebuild all entities\n")
    
    # Determine which entities to build
    if args.entity_type:
        types_to_build = [args.entity_type]
    else:
        # Get all entity types from config
        from app.knowledge_base.entity_config import load_entity_config
        config_map = load_entity_config()
        all_types = list(config_map.keys())
        
        # If resume flag is set, only build remaining entities
        if args.resume:
            types_to_build = get_remaining_entities(all_types)
        else:
            types_to_build = all_types
    
    print(f"Starting KB Rebuild Script...")
    if args.resume:
        print(f"[RESUME MODE] Resuming from checkpoint\n")
    asyncio.run(build_entity_kb(target_entity_types=types_to_build, use_checkpoint=True))
    
    print(f"\nKB Rebuild Script Finished.")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    main()
