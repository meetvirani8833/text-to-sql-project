from typing import List, Dict, Any
from neo4j.exceptions import ServiceUnavailable, SessionExpired
from app.dependencies import get_neo4j_driver, reset_neo4j_driver

def _is_neo4j_connection_error(e: Exception) -> bool:
    """Check if the exception is a Neo4j connection/routing error (Aura auto-suspend)."""
    return isinstance(e, (ServiceUnavailable, SessionExpired)) or \
        "ServiceUnavailable" in type(e).__name__ or \
        "SessionExpired" in type(e).__name__

def upsert_table_node(table_name: str):
    driver = get_neo4j_driver()
    query = "MERGE (t:Table {name: $name})"
    with driver.session() as session:
        session.run(query, name=table_name)

def upsert_fk_edge(from_table: str, from_col: str, to_table: str, to_col: str):
    """
    Creates a FK relationship: (:Table {name: from_table})-[:FK {from_col, to_col}]->(:Table {name: to_table})
    Both nodes must exist (upsert_table_node should be called first).
    """
    driver = get_neo4j_driver()
    query = """
    MATCH (a:Table {name: $from_table})
    MATCH (b:Table {name: $to_table})
    MERGE (a)-[r:FK {from_col: $from_col, to_col: $to_col}]->(b)
    """
    with driver.session() as session:
        session.run(query, from_table=from_table, to_table=to_table, from_col=from_col, to_col=to_col)

def find_join_path(table_a: str, table_b: str) -> List[Dict[str, Any]]:
    """
    Finds the shortest path between two tables using FK relationships.
    Relationships are treated as undirected for the purpose of joining (A->B or B->A both allow joining).
    Retries once on connection errors (Neo4j Aura auto-suspend).
    """
    query = """
    MATCH (start:Table {name: $start_name}), (end:Table {name: $end_name})
    MATCH p = shortestPath((start)-[:FK*]-(end))
    RETURN p
    """
    for attempt in range(2):
        try:
            driver = get_neo4j_driver()
            with driver.session() as session:
                result = session.run(query, start_name=table_a, end_name=table_b)
                record = result.single()
                if not record:
                    return []

                path = record["p"]
                steps = []
                for rel in path.relationships:
                     steps.append({
                         "start": rel.start_node["name"],
                         "end": rel.end_node["name"],
                         "from_col": rel["from_col"],
                         "to_col": rel["to_col"]
                     })
                return steps
        except Exception as e:
            if attempt == 0 and _is_neo4j_connection_error(e):
                print(f"  Neo4j Aura connection was suspended, reconnecting... ({e})")
                reset_neo4j_driver()
                continue
            raise
    return []

def find_multi_table_join(tables: List[str]) -> List[Dict[str, Any]]:
    """
    For a list of tables > 2, finds a connected subgraph joining all of them.
    Simplified approach: Find a Steiner Tree approximation or just pair-wise paths.
    
    This is complex. For now, we will implement a basic strategy:
    1. Pick the first table as 'center'.
    2. Find paths from center to all other tables.
    3. Merge paths.
    
    Better approach for SQL generation:
    We need an ordered sequence of joins.
    """
    if not tables:
        return []
        
    # Placeholder for complex logic. 
    # Returning empty for now as it requires significant graph algorithm implementation
    # which we can refine when we get to the Workflow phase.
    return []

