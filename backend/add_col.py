import asyncio
from sqlalchemy import text
from app.dependencies import AsyncSessionLocal

async def add_column():
    async with AsyncSessionLocal() as session:
        try:
            await session.execute(text("ALTER TABLE column_meta ADD COLUMN visualization_name VARCHAR"))
            await session.commit()
            print("Successfully added visualization_name column!")
        except Exception as e:
            print("Column may already exist or error occurred:", e)

if __name__ == "__main__":
    asyncio.run(add_column())
