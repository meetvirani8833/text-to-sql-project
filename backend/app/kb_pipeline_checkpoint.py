"""
Checkpoint system for main KB rebuild pipeline.
Allows resuming from where it left off instead of restarting.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

CHECKPOINT_DIR = Path(__file__).parent / ".rebuild_checkpoints"
CHECKPOINT_DIR.mkdir(exist_ok=True)

def get_kb_checkpoint_file() -> Path:
    """Get checkpoint file path for main KB rebuild."""
    return CHECKPOINT_DIR / "kb_rebuild_checkpoint.json"

def load_kb_checkpoint() -> Optional[Dict[str, Any]]:
    """Load KB checkpoint if it exists."""
    checkpoint_file = get_kb_checkpoint_file()
    if checkpoint_file.exists():
        try:
            with open(checkpoint_file, 'r') as f:
                data = json.load(f)
                print(f"[KB-CHECKPOINT] Loaded checkpoint from {checkpoint_file.name}")
                print(f"[KB-CHECKPOINT] Completed: {', '.join(data.get('completed_tables', []))}")
                return data
        except Exception as e:
            print(f"[KB-CHECKPOINT] Error loading checkpoint: {e}")
            return None
    return None

def save_kb_checkpoint(completed_tables: List[str], total_tables: List[str], 
                       current_table: Optional[str] = None) -> None:
    """Save KB rebuild progress checkpoint."""
    checkpoint_file = get_kb_checkpoint_file()
    checkpoint_data = {
        "timestamp": datetime.now().isoformat(),
        "completed_tables": completed_tables,
        "total_tables": total_tables,
        "current_table": current_table,
        "progress": f"{len(completed_tables)}/{len(total_tables)}"
    }
    
    try:
        with open(checkpoint_file, 'w') as f:
            json.dump(checkpoint_data, f, indent=2)
        print(f"[KB-CHECKPOINT] Progress saved: {len(completed_tables)}/{len(total_tables)} tables")
    except Exception as e:
        print(f"[KB-CHECKPOINT] Error saving checkpoint: {e}")

def get_remaining_kb_tables(all_tables: List[str]) -> List[str]:
    """Get list of tables still needing processing."""
    checkpoint = load_kb_checkpoint()
    if checkpoint:
        completed = checkpoint.get('completed_tables', [])
        remaining = [t for t in all_tables if t not in completed]
        print(f"[KB-CHECKPOINT] Resuming with {len(remaining)} remaining tables")
        return remaining
    return all_tables

def mark_kb_table_complete(table: str, completed_list: List[str], total_list: List[str]) -> List[str]:
    """Mark a table as complete and save checkpoint."""
    completed_list.append(table)
    save_kb_checkpoint(completed_list, total_list, current_table=None)
    return completed_list

def clear_kb_checkpoint() -> None:
    """Clear KB checkpoint to force full rebuild."""
    checkpoint_file = get_kb_checkpoint_file()
    if checkpoint_file.exists():
        checkpoint_file.unlink()
        print("[KB-CHECKPOINT] Checkpoint cleared - will rebuild all tables")

def get_kb_checkpoint_stats() -> Optional[Dict[str, Any]]:
    """Get current KB checkpoint statistics."""
    checkpoint_file = get_kb_checkpoint_file()
    if checkpoint_file.exists():
        try:
            with open(checkpoint_file, 'r') as f:
                return json.load(f)
        except:
            return None
    return None

def print_kb_checkpoint_status() -> None:
    """Print current KB checkpoint status."""
    stats = get_kb_checkpoint_stats()
    if stats:
        print("\n" + "=" * 60)
        print("KB REBUILD CHECKPOINT STATUS")
        print("=" * 60)
        print(f"Last updated: {stats.get('timestamp', 'N/A')}")
        print(f"Progress: {stats.get('progress', 'N/A')}")
        print(f"Completed tables:")
        for table in stats.get('completed_tables', []):
            print(f"  ✓ {table}")
        if stats.get('total_tables'):
            remaining = [t for t in stats['total_tables'] if t not in stats.get('completed_tables', [])]
            if remaining:
                print(f"Remaining tables:")
                for table in remaining:
                    print(f"  ○ {table}")
        print("=" * 60 + "\n")
    else:
        print("\n[KB-CHECKPOINT] No checkpoint found\n")
