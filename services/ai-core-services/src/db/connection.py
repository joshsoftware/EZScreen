from typing import Any, AsyncGenerator, Optional
from sqlalchemy import text, create_engine
from sqlalchemy.orm import sessionmaker
from src.core.config import settings
from src.core.logger import logger


def _get_sqlalchemy_url() -> str:
    return settings.database_url

try:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    
    async_url = _get_sqlalchemy_url()
    if async_url.startswith("postgresql://"):
        async_url = async_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    engine = create_async_engine(async_url, pool_pre_ping=True)
    AsyncSessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    HAS_ASYNC = True
except Exception:
    HAS_ASYNC = False
    sync_url = _get_sqlalchemy_url()
    engine = create_engine(sync_url, pool_pre_ping=True)
    AsyncSessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[Any, None]:
    if HAS_ASYNC:
        async with AsyncSessionLocal() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
    else:
        with AsyncSessionLocal() as session:
            try:
                yield session
            except Exception:
                session.rollback()
                raise


async def close_engine() -> None:
    if HAS_ASYNC:
        await engine.dispose()
    else:
        engine.dispose()
    logger.info("Database engine disposed")


async def test_db_connection() -> Any:
    try:
        if HAS_ASYNC:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        else:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error("Database connection failed: %s", e)
        return False
