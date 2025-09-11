"""
Database configuration and session management
"""
from sqlmodel import create_engine, SQLModel, Session
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

# Sync engine for migrations and simple operations
engine = create_engine(
    str(settings.DATABASE_URL),
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10
)

# Async engine for async endpoints
async_engine = create_async_engine(
    str(settings.DATABASE_URL).replace("postgresql://", "postgresql+asyncpg://"),
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10
)

# Session makers
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    class_=Session,
    expire_on_commit=False
)

AsyncSessionLocal = sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


def get_session():
    """Dependency to get DB session"""
    with Session(engine) as session:
        yield session


async def get_async_session():
    """Dependency to get async DB session"""
    async with AsyncSessionLocal() as session:
        yield session


def init_db():
    """Initialize database tables"""
    # In production, you'll use Flyway/Alembic migrations
    # This is just for development
    SQLModel.metadata.create_all(engine)
