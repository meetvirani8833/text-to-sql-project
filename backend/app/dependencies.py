from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from urllib.parse import quote_plus
from app.config import settings
from app.knowledge_base.models import Base

# Postgres Connection String
# postgresql+asyncpg://user:password@host:port/db
def get_postgres_url():
    base = (
        f"postgresql+asyncpg://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@"
        f"{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
    )
    if settings.POSTGRES_SSLMODE:
        return f"{base}?ssl={settings.POSTGRES_SSLMODE}"
    return base

engine = create_async_engine(get_postgres_url(), echo=False, pool_pre_ping=True, pool_recycle=270)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

async def init_db():
    async with engine.begin() as conn:
        # Create all tables defined in models.py (imported via Base)
        await conn.run_sync(Base.metadata.create_all)

from neo4j import GraphDatabase
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from sqlalchemy import create_engine, inspect

# ... Postgres logic (unchanged) ...

# Neo4j Driver (singleton — reuse across the process to avoid repeated TLS handshakes)
_neo4j_driver = None

def get_neo4j_driver():
    global _neo4j_driver
    if _neo4j_driver is None:
        _neo4j_driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        )
    return _neo4j_driver

def reset_neo4j_driver():
    """Close and invalidate the Neo4j driver singleton so it reconnects on next use."""
    global _neo4j_driver
    if _neo4j_driver is not None:
        try:
            _neo4j_driver.close()
        except Exception:
            pass
        _neo4j_driver = None

# LangChain LLM & Embeddings
def get_llm():
    return ChatOpenAI(
        model_name="gpt-4o-mini",
        temperature=0,
        openai_api_key=settings.OPENAI_API_KEY
    )

def get_llm_4o():
    return ChatOpenAI(
        model_name="gpt-4o",
        temperature=0,
        openai_api_key=settings.OPENAI_API_KEY
    )

def get_llm_o4_mini():
    return ChatOpenAI(
        model_name="o4-mini",
        openai_api_key=settings.OPENAI_API_KEY
    )

# Incorporating new relevant LLMs

# Can easily replace gpt 4o
def get_llm_gpt_5_mini():
    return ChatOpenAI(
        model_name="gpt-5-mini",
        openai_api_key=settings.OPENAI_API_KEY
    )

# The one that will replace gpt-4o-mini
def get_llm_gpt_5_nano():
    return ChatOpenAI(
        model_name="gpt-5-nano",
        openai_api_key=settings.OPENAI_API_KEY,
        reasoning_effort="low"
    )

# The one that can replace o4-mini or gpt-4o
def get_llm_gpt_5():
    return ChatOpenAI(
        model_name="gpt-5.1",
        openai_api_key=settings.OPENAI_API_KEY
    )

def get_embeddings():
    return OpenAIEmbeddings(
        model="text-embedding-3-small",
        openai_api_key=settings.OPENAI_API_KEY
    )

# MySQL Introspection
def get_mysql_inspector():
    # Use pymysql sync driver for introspection
    encoded_password = quote_plus(settings.MYSQL_PASSWORD)
    url = f"mysql+pymysql://{settings.MYSQL_USER}:{encoded_password}@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
    engine = create_engine(url)
    return inspect(engine)
