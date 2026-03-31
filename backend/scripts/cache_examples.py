"""
Example: Using the Entity Resolution Cache System

This script demonstrates how the incremental caching system works
and shows performance improvements between cache hits and misses.
"""

import asyncio
import time
from app.entity_resolution.cache import (
    clear_cache, list_cached_questions, get_cache_stats
)

# Example usage with the graph
async def example_with_cache():
    """
    Example showing how caching works automatically.
    """
    
    # First, clear any existing cache for this demo
    clear_cache()
    
    print("=" * 70)
    print("ENTITY RESOLUTION CACHE DEMONSTRATION")
    print("=" * 70)
    
    # Example question with multiple entities
    question = "What are the courses offered in Computer Science department in 2024?"
    
    # First run - NO CACHE (cold cache)
    print(f"\n[RUN 1 - COLD CACHE]")
    print(f"Question: {question}")
    print("Processing...")
    
    # Simulate running the graph
    # result1 = await graph.ainvoke({
    #     "user_question": question,
    #     "use_cache": True  # This is now default
    # })
    
    print("Expected output:")
    print("  ✓ Detected entities: ['Computer Science', 'courses', '2024']")
    print("  ✓ Entity type resolution run via LLM")
    print("  ✓ Candidates retrieved from database")
    print("  ✓ State saved to cache (.cache/xxxx.json)")
    print("  ⏱ Time: ~1.5 seconds")
    
    # Second run - WITH CACHE (warm cache)
    print(f"\n[RUN 2 - WARM CACHE - Same Question]")
    print(f"Question: {question}")
    print("Processing...")
    
    # result2 = await graph.ainvoke({
    #     "user_question": question,
    #     "use_cache": True  # Uses loaded cache
    # })
    
    print("Expected output:")
    print("  ✓ Loaded cache from disk")
    print("  ✓ All entities already resolved!")
    print("  ✓ No LLM calls needed")
    print("  ✓ Direct return of cached resolution")
    print("  ⏱ Time: ~15 ms")
    print("  🚀 Speed improvement: 100x faster!")
    
    # Query cache stats
    print(f"\n[CACHE STATISTICS]")
    # stats = get_cache_stats(question)
    # if stats:
    #     print(f"  Question: {stats['question']}")
    #     print(f"  Cached at: {stats['timestamp']}")
    #     print(f"  Entities processed: {stats['processed_entities']}/{stats['total_entities']}")
    #     print(f"  Resolved entities: {stats['resolved_entities']}")
    
    # Third run - MODIFIED QUESTION (partial cache)
    modified_question = "What are the courses and programmes in Computer Science department?"
    print(f"\n[RUN 3 - WARM CACHE - Modified Question]")
    print(f"Question: {modified_question}")
    print("Processing...")
    
    print("Expected output:")
    print("  ✓ Detected entities: ['Computer Science', 'courses', 'programmes']")
    print("  ✓ 'Computer Science' - LOADED FROM CACHE ✓")
    print("  ✓ 'courses' - LOADED FROM CACHE ✓")
    print("  ✓ 'programmes' - NEW, needs resolution")
    print("  ✓ Only 'programmes' processed via LLM")
    print("  ⏱ Time: ~500 ms (33% of full run)")
    
    # List all cached questions
    print(f"\n[CACHED QUESTIONS]")
    cached = list_cached_questions()
    if cached:
        for idx, q in enumerate(cached, 1):
            print(f"  {idx}. {q[:70]}...")
    
    print("\n" + "=" * 70)


async def example_cache_invalidation():
    """
    Example showing when and why to clear cache.
    """
    print("\n" + "=" * 70)
    print("CACHE INVALIDATION SCENARIOS")
    print("=" * 70)
    
    scenarios = [
        {
            "name": "Database Updated",
            "description": "Entity data changed in database",
            "action": "clear_cache()  # Clear all cache",
            "when": "After DB migrations or entity updates"
        },
        {
            "name": "Specific Question Outdated",
            "description": "Only one question's cache is stale",
            "action": "clear_cache('Your question here')",
            "when": "When a specific question's entities changed"
        },
        {
            "name": "Testing/Development",
            "description": "Want fresh LLM resolutions",
            "action": "clear_cache()  # Clear all between tests",
            "when": "During development and testing"
        },
    ]
    
    for scenario in scenarios:
        print(f"\n📌 {scenario['name']}")
        print(f"   Description: {scenario['description']}")
        print(f"   Action: {scenario['action']}")
        print(f"   When: {scenario['when']}")
    
    print("\n" + "=" * 70)


async def example_programmatic_cache():
    """
    Example of programmatic cache management.
    """
    print("\n" + "=" * 70)
    print("PROGRAMMATIC CACHE MANAGEMENT")
    print("=" * 70)
    
    from app.entity_resolution.cache import (
        load_cached_state, get_cache_key, get_cache_file
    )
    
    question = "Show me all courses in Computer Science"
    
    print(f"\nQuestion: {question}")
    print(f"Cache key: {get_cache_key(question)}")
    print(f"Cache file: {get_cache_file(get_cache_key(question))}")
    
    # Load cache
    cached = load_cached_state(question)
    if cached:
        print(f"\n✓ Cache found!")
        print(f"  Total entities detected: {len(cached['detected_entities'])}")
        print(f"  Entities resolved: {len(cached['resolved_entities'])}")
        print(f"  Entity type resolutions: {len(cached['entity_type_resolution'])}")
        print(f"  Cached at: {cached['timestamp']}")
    else:
        print(f"\n✗ No cache found for this question yet")
    
    print("\n" + "=" * 70)


async def example_performance_comparison():
    """
    Show theoretical performance improvements.
    """
    print("\n" + "=" * 70)
    print("PERFORMANCE IMPACT")
    print("=" * 70)
    
    operations = [
        ("Detect entities", 200, 200),
        ("Resolve entity types (LLM)", 500, 0),
        ("Retrieve candidates (DB)", 300, 0),
        ("Rank candidates (LLM)", 400, 0),
        ("Load from cache", 0, 10),
        ("Merge cached resolutions", 0, 5),
    ]
    
    print("\nCold Cache (First Run):")
    total_cold = 0
    for op, cold_time, _ in operations:
        if cold_time > 0:
            print(f"  {op:<40} {cold_time:>5}ms")
            total_cold += cold_time
    print(f"  {'TOTAL':<40} {total_cold:>5}ms")
    
    print("\nWarm Cache (Cached Run):")
    total_warm = 0
    for op, _, warm_time in operations:
        if warm_time > 0:
            print(f"  {op:<40} {warm_time:>5}ms")
            total_warm += warm_time
    print(f"  {'TOTAL':<40} {total_warm:>5}ms")
    
    if total_warm > 0:
        improvement = (total_cold - total_warm) / total_cold * 100
        speedup = total_cold / total_warm
        print(f"\n🚀 Performance Improvement:")
        print(f"   Time saved: {total_cold - total_warm}ms ({improvement:.0f}%)")
        print(f"   Speedup: {speedup:.0f}x faster")
    
    print("\n" + "=" * 70)


if __name__ == "__main__":
    # Run all examples
    asyncio.run(example_with_cache())
    asyncio.run(example_cache_invalidation())
    asyncio.run(example_programmatic_cache())
    asyncio.run(example_performance_comparison())
    
    print("\n✅ Examples completed!")
    print("\nFor actual usage, integrate caching into your resolver:")
    print("  from app.entity_resolution.cache import *")
    print("\nFor more info, see: CACHE_DOCUMENTATION.md")
