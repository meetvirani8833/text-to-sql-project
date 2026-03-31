"""
Checkpoint system for entity KB rebuild pipeline.
Allows resuming from where it left off instead of restarting.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

CHECKPOINT_DIR = Path(__file__).parent / ".rebuild_checkpoints"
CHECKPOINT_DIR.mkdir(exist_ok=True)

def get_checkpoint_file() -> Path:
    """Get checkpoint file path."""
    return CHECKPOINT_DIR / "entity_rebuild_checkpoint.json"

def load_checkpoint() -> Optional[Dict[str, Any]]:
    """Load checkpoint if it exists."""
    checkpoint_file = get_checkpoint_file()
    if checkpoint_file.exists():
        try:
            with open(checkpoint_file, 'r') as f:
                data = json.load(f)
                print(f"[CHECKPOINT] Loaded checkpoint from {checkpoint_file.name}")
                print(f"[CHECKPOINT] Completed: {', '.join(data.get('completed_entities', []))}")
                return data
        except Exception as e:
            print(f"[CHECKPOINT] Error loading checkpoint: {e}")
            return None
    return None

def save_checkpoint(completed_entities: List[str], total_entities: List[str], 
                   current_entity: Optional[str] = None) -> None:
    """Save rebuild progress checkpoint."""
    checkpoint_file = get_checkpoint_file()
    checkpoint_data = {
        "timestamp": datetime.now().isoformat(),
        "completed_entities": completed_entities,
        "total_entities": total_entities,
        "current_entity": current_entity,
        "progress": f"{len(completed_entities)}/{len(total_entities)}"
    }
    
    try:
        with open(checkpoint_file, 'w') as f:
            json.dump(checkpoint_data, f, indent=2)
        print(f"[CHECKPOINT] Progress saved: {len(completed_entities)}/{len(total_entities)} entities")
    except Exception as e:
        print(f"[CHECKPOINT] Error saving checkpoint: {e}")

def get_remaining_entities(all_entities: List[str]) -> List[str]:
    """Get list of entities still needing processing."""
    checkpoint = load_checkpoint()
    if checkpoint:
        completed = checkpoint.get('completed_entities', [])
        remaining = [e for e in all_entities if e not in completed]
        print(f"[CHECKPOINT] Resuming with {len(remaining)} remaining entities")
        return remaining
    return all_entities

def mark_entity_complete(entity: str, completed_list: List[str], total_list: List[str]) -> List[str]:
    """Mark an entity as complete and save checkpoint."""
    completed_list.append(entity)
    save_checkpoint(completed_list, total_list, current_entity=None)
    return completed_list

def clear_checkpoint() -> None:
    """Clear checkpoint to force full rebuild."""
    checkpoint_file = get_checkpoint_file()
    if checkpoint_file.exists():
        checkpoint_file.unlink()
        print("[CHECKPOINT] Checkpoint cleared - will rebuild all entities")

def get_checkpoint_stats() -> Optional[Dict[str, Any]]:
    """Get current checkpoint statistics."""
    checkpoint_file = get_checkpoint_file()
    if checkpoint_file.exists():
        try:
            with open(checkpoint_file, 'r') as f:
                return json.load(f)
        except:
            return None
    return None

def print_checkpoint_status() -> None:
    """Print current checkpoint status."""
    stats = get_checkpoint_stats()
    if stats:
        print("\n" + "=" * 60)
        print("REBUILD CHECKPOINT STATUS")
        print("=" * 60)
        print(f"Last updated: {stats.get('timestamp', 'N/A')}")
        print(f"Progress: {stats.get('progress', 'N/A')}")
        print(f"Completed entities:")
        for entity in stats.get('completed_entities', []):
            print(f"  ✓ {entity}")
        if stats.get('total_entities'):
            remaining = [e for e in stats['total_entities'] if e not in stats.get('completed_entities', [])]
            if remaining:
                print(f"Remaining entities:")
                for entity in remaining:
                    print(f"  ○ {entity}")
        print("=" * 60 + "\n")
    else:
        print("\n[CHECKPOINT] No checkpoint found\n")
