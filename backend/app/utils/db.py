from functools import lru_cache
from sqlalchemy import create_engine
from urllib.parse import quote_plus
from app.config import settings

@lru_cache(maxsize=1)
def get_mysql_engine():
    """Return a singleton SQLAlchemy engine for the source MySQL database."""
    if not settings.MYSQL_USER:
         return None

    encoded_password = quote_plus(settings.MYSQL_PASSWORD)
    url = (
        f"mysql+pymysql://{settings.MYSQL_USER}:{encoded_password}"
        f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
    )
    return create_engine(url, pool_size=3, max_overflow=2, pool_recycle=1800)