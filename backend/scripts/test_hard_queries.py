import asyncio
import sys
import os
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.workflow.graph import compiled_graph
from app.dependencies import get_llm, get_embeddings, get_neo4j_driver
from app.utils.db import get_mysql_engine

QUERIES = [
    ("Q1  - Academic Structure Logic",         "List all courses that include both theory and practical components offered by the School of Engineering."),
    ("Q2  - Duplicate Course Names",            "Find course names that are offered by more than one department."),
    ("Q3  - Programme vs Add-on",               "How many add-on courses are offered by each department?"),
    ("Q4  - Curriculum Evolution",              "List courses introduced after 2020 that are still active."),
    ("Q5  - Second Language + FK Awareness",    "Show all second language courses along with their language identifiers."),
    ("Q6  - Department Load Analysis",          "Which department offers the highest number of practical courses?"),
    ("Q7  - School-Level Courses",              "Retrieve courses offered at the school level instead of specific departments."),
    ("Q8  - Course Code Pattern",               'Find all courses whose code ends with "L" (lab-oriented courses).'),
    ("Q9  - Cross Classification Logic",        "Count courses by course type and indicate whether they are theory, practical, or both."),
    ("Q10 - Academic Hierarchy Summary",        "Provide the number of active courses under each deanery."),
    ("Q11 - Data Quality Detection",            "Identify course codes that are assigned to multiple course names."),
    ("Q12 - Rare Course Type Discovery",        "List course types that have fewer than 50 courses."),
    ("Q13 - Combined Academic Logic",           "List all active programme courses offered by the School of Sciences that include practical components."),
    ("Q14 - Missing Department Assignment",     "Find courses that do not have an assigned offering department."),
    ("Q15 - Curriculum Distribution by Year",   "Show the number of courses introduced each year."),
    ("Q16 - Academic Portfolio Complexity",     "Which deanery offers the widest variety of course types?"),
    ("Q17 - Theory-Practical Parent Mapping",   "List courses where the theory parent type differs from the practical parent type."),
    ("Q18 - Curriculum Standardization Check",  "Find courses where the course type indicates practical but theory_or_practical is marked as theory."),
]

PASS = "✅ PASS"
FAIL = "❌ FAIL"

async def run_query(label: str, question: str, llm, embeddings, neo4j_driver, mysql_engine) -> dict:
    inputs = {
        "user_question": question,
        "llm": llm,
        "embeddings": embeddings,
        "neo4j_driver": neo4j_driver,
        "mysql_engine": mysql_engine,
        "retry_count": 0,
        "selected_tables": [],
        "candidate_tables": [],
        "table_metadata": [],
        "join_paths": [],
        "applicable_rules": []
    }
    
    sql = None
    summary = None
    error = None
    
    try:
        async for output in compiled_graph.astream(inputs):
            for node_name, value in output.items():
                if "generated_sql" in value:
                    sql = value["generated_sql"]
                if "result_summary" in value:
                    summary = value["result_summary"]
                if "error_details" in value and value["error_details"]:
                    error = value["error_details"]
    except Exception as e:
        error = str(e)
    
    return {"label": label, "question": question, "sql": sql, "summary": summary, "error": error}


async def main():
    print("=" * 70)
    print("  HARD TEST SUITE - aca_course  ")
    print("=" * 70)
    
    llm = get_llm()
    embeddings = get_embeddings()
    neo4j_driver = get_neo4j_driver()
    mysql_engine = get_mysql_engine()
    
    results = []
    
    for label, question in QUERIES:
        print(f"\n{'─' * 70}")
        print(f"🧪 {label}")
        print(f"   Q: {question}")
        
        start = time.time()
        result = await run_query(label, question, llm, embeddings, neo4j_driver, mysql_engine)
        elapsed = time.time() - start
        
        if result["sql"]:
            print(f"   SQL: {result['sql']}")
        
        if result["summary"]:
            print(f"   {PASS} ({elapsed:.1f}s)")
            print(f"   Answer: {result['summary'][:300]}{'...' if len(result.get('summary','')) > 300 else ''}")
            result["status"] = "PASS"
        else:
            print(f"   {FAIL} ({elapsed:.1f}s)")
            if result["error"]:
                print(f"   Error: {result['error'][:200]}")
            result["status"] = "FAIL"
        
        results.append(result)
    
    # Summary table
    print(f"\n{'=' * 70}")
    print("  RESULTS SUMMARY")
    print(f"{'=' * 70}")
    passed = sum(1 for r in results if r["status"] == "PASS")
    total = len(results)
    for r in results:
        icon = "✅" if r["status"] == "PASS" else "❌"
        print(f"  {icon} {r['label']}")
    print(f"\n  Score: {passed}/{total} passed")
    print("=" * 70)


if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
