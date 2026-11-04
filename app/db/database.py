# from sqlalchemy.ext.asyncio import (
#     AsyncSession,
#     async_sessionmaker,
#     create_async_engine,
# )
# from sqlalchemy.orm import DeclarativeBase

# from app.core.config import settings


# class Base(DeclarativeBase):
#     pass


# engine = create_async_engine(
#     settings.DATABASE_URL,
#     echo=settings.DEBUG,
# )

# AsyncSessionLocal = async_sessionmaker(
#     bind=engine,
#     class_=AsyncSession,
#     expire_on_commit=False,
# )


# async def get_db():
#     async with AsyncSessionLocal() as session:
#         yield session


from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    sessionmaker,
)

from app.core.config import settings


class Base(DeclarativeBase):
    pass


# =========================================================
# ASYNC DATABASE
# Used by FastAPI endpoints/services
# =========================================================

async_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


# =========================================================
# SYNC DATABASE
# Used by Celery workers
# =========================================================

SYNC_DATABASE_URL = settings.DATABASE_URL.replace(
    "+asyncpg",
    "",
)

sync_engine = create_engine(
    SYNC_DATABASE_URL,
    echo=settings.DEBUG,
)

SyncSessionLocal = sessionmaker(
    bind=sync_engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)
