#!/usr/bin/env python
"""
Utility script to manage entity resolution cache.
Usage:
    python manage_cache.py list      - List all cached questions
    python manage_cache.py info <question>  - Show cache stats for a question
    python manage_cache.py clear [question] - Clear cache (all or specific)
"""

import sys
import argparse
from app.entity_resolution.cache import (
    list_cached_questions, get_cache_stats, clear_cache
)

def main():
    parser = argparse.ArgumentParser(description="Manage entity resolution cache")
    subparsers = parser.add_subparsers(dest="command", help="Cache operation")
    
    # list command
    subparsers.add_parser("list", help="List all cached questions")
    
    # info command
    info_parser = subparsers.add_parser("info", help="Show cache stats for a question")
    info_parser.add_argument("question", type=str, help="Question to get stats for")
    
    # clear command
    clear_parser = subparsers.add_parser("clear", help="Clear cache")
    clear_parser.add_argument("question", nargs="?", default=None, help="Specific question to clear (optional)")
    
    args = parser.parse_args()
    
    if args.command == "list":
        questions = list_cached_questions()
        if questions:
            print("Cached questions:")
            for i, q in enumerate(questions, 1):
                print(f"  {i}. {q[:80]}{'...' if len(q) > 80 else ''}")
        else:
            print("No cached items")
            
    elif args.command == "info":
        stats = get_cache_stats(args.question)
        if stats:
            print(f"Cache stats for: {stats['question']}")
            print(f"  Timestamp: {stats['timestamp']}")
            print(f"  Processed entities: {stats['processed_entities']}/{stats['total_entities']}")
            print(f"  Resolved entities: {stats['resolved_entities']}")
        else:
            print(f"No cache found for: {args.question}")
            
    elif args.command == "clear":
        if args.question:
            clear_cache(args.question)
        else:
            response = input("Clear ALL cache? (y/N): ").lower()
            if response == 'y':
                clear_cache()
            else:
                print("Cancelled")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
