from pydantic_settings import BaseSettings, SettingsConfigDict
import os

class Settings(BaseSettings):
    # API Keys
    OPENAI_API_KEY: str = ""

    # LangSmith / LangChain Tracing
    LANGSMITH_API_KEY: str = ""
    LANGSMITH_PROJECT: str = "curriculum-agent"
    LANGCHAIN_API_KEY: str = ""
    LANGCHAIN_PROJECT: str = "curriculum-agent"
    LANGCHAIN_TRACING_V2: str = "false"

    # Source DB (MySQL)
    MYSQL_HOST: str = ""
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = ""
    MYSQL_PASSWORD: str = ""
    MYSQL_DATABASE: str = ""

    # Metadata DB (PostgreSQL)
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "curriculum"
    POSTGRES_PASSWORD: str = ""
    POSTGRES_DB: str = "curriculum_kb"
    POSTGRES_SSLMODE: str = ""

    # Neo4j
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = ""

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"),
        env_file_encoding="utf-8", 
        extra="ignore"
    )

settings = Settings()

def configure_langsmith():
    """Set os.environ vars required by LangChain for auto-tracing."""
    # LangChain reads LANGCHAIN_API_KEY and LANGCHAIN_TRACING_V2 from os.environ
    api_key = settings.LANGCHAIN_API_KEY or settings.LANGSMITH_API_KEY
    if api_key:
        os.environ["LANGCHAIN_API_KEY"] = api_key
        os.environ["LANGCHAIN_TRACING_V2"] = settings.LANGCHAIN_TRACING_V2
        os.environ["LANGCHAIN_PROJECT"] = settings.LANGCHAIN_PROJECT or settings.LANGSMITH_PROJECT

# Auto-configure at import time so all LangChain components are traced
configure_langsmith()
