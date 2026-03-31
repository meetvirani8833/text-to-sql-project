import asyncio
import sys
import os
from sqlalchemy import text

# Add backend to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.dependencies import get_neo4j_driver, AsyncSessionLocal
from app.knowledge_base.kb_pipeline import rebuild_all
from app.config import settings

async def wipe_postgres():
    print("Wiping Postgres Metadata...")
    async with AsyncSessionLocal() as session:
        # Truncate tables. CASCADE handles FKs.
        await session.execute(text("TRUNCATE TABLE table_meta CASCADE;"))
        # Clean up vector store tables if needed. 
        # PGVector usually uses `langchain_pg_embedding` and `langchain_pg_collection`.
        # We can try truncating them or rely on vector store logic.
        # Let's try to clear them to be safe.
        try:
            await session.execute(text("TRUNCATE TABLE langchain_pg_embedding CASCADE;"))
            await session.execute(text("TRUNCATE TABLE langchain_pg_collection CASCADE;"))
        except Exception as e:
            print(f"Warning clearing vector store (might not exist yet): {e}")

        await session.commit()
    print("Postgres Wiped.")

def wipe_neo4j():
    print("Wiping Neo4j Graph...")
    driver = get_neo4j_driver()
    with driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")
    print("Neo4j Wiped.")

async def main():
    print("Starting Knowledge Base Clean up...")
    
    # 1. Wipe Data
    await wipe_postgres()
    wipe_neo4j()

    print("Knowledge Base is not empty...")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
