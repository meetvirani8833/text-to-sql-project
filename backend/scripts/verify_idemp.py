import asyncio
import sys
from pathlib import Path

# Add the backend dir to sys.path so we can import 'app'
backend_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(backend_dir))

from app.dependencies import AsyncSessionLocal
from sqlalchemy import text

async def test_idempotency():
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("SELECT alias, COUNT(*) FROM entity_aliases WHERE entity_type='department' GROUP BY alias HAVING COUNT(*)>1;"))
        dupes = result.fetchall()
        print(f'Duplicate department aliases found: {len(dupes)}')
        if len(dupes) > 0: 
            print(f'Sample: {dupes[:3]}')

if __name__ == "__main__":
    asyncio.run(test_idempotency())
