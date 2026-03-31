import asyncio
import sys
from pathlib import Path

# Add the backend dir to sys.path so we can import 'app'
backend_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(backend_dir))

from app.dependencies import AsyncSessionLocal
from sqlalchemy import text

async def check_db():
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("SELECT entity_type, alias, canonical_name, source FROM entity_aliases WHERE entity_type='department' LIMIT 5;"))
        for row in result: 
            print(row)

if __name__ == "__main__":
    asyncio.run(check_db())
