"""
Enhanced database configuration with connection pooling, retry logic, and proper async handling
"""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy import event, pool, text
from sqlalchemy.exc import DBAPIError, DisconnectionError, OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlmodel import SQLModel, create_engine
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.logging import log


class DatabaseConfig:
    """Database configuration with environment-based settings"""
    
    def __init__(self):
        self.database_url = settings.database_url
        self.pool_size = settings.db_pool_size
        self.max_overflow = settings.db_max_overflow
        self.pool_pre_ping = settings.db_pool_pre_ping
        self.echo = settings.db_echo
        
        # Advanced pool settings
        self.pool_recycle = 3600  # Recycle connections after 1 hour
        self.pool_timeout = 30    # Pool timeout in seconds
        self.connect_timeout = 10 # Connection timeout
        
    @property
    def async_url(self) -> str:
        """Convert sync URL to async URL"""
        return str(self.database_url).replace("postgresql://", "postgresql+asyncpg://")
        
    @property
    def sync_engine_kwargs(self) -> dict:
        """Get sync engine configuration"""
        return {
            "echo": self.echo,
            "pool_pre_ping": self.pool_pre_ping,
            "pool_size": self.pool_size,
            "max_overflow": self.max_overflow,
            "poolclass": pool.QueuePool,
            "pool_recycle": self.pool_recycle,
            "pool_timeout": self.pool_timeout,
            "connect_args": {
                "connect_timeout": self.connect_timeout
            }
        }
        
    @property
    def async_engine_kwargs(self) -> dict:
        """Get async engine configuration"""
        kwargs = self.sync_engine_kwargs.copy()
        # Remove poolclass for async engine (not compatible)
        kwargs.pop("poolclass", None)
        kwargs["connect_args"] = {
            "server_settings": {
                "application_name": settings.app_name,
                "jit": "off"
            }
        }
        return kwargs


# Initialize configuration
db_config = DatabaseConfig()

# Create engines with proper configuration
engine = create_engine(
    str(db_config.database_url),
    **db_config.sync_engine_kwargs
)

async_engine = create_async_engine(
    db_config.async_url,
    **db_config.async_engine_kwargs
)


# Enhanced session factories with proper configuration
SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False
)


# Connection event handlers for resilience
@event.listens_for(pool.Pool, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Set connection parameters on connect"""
    # This is called for each new connection
    if settings.database_url.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


@event.listens_for(engine, "connect")
def receive_connect(dbapi_connection, connection_record):
    """Log new connections"""
    log.debug("New database connection established")


# Retry decorator for database operations
db_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
    retry=(OperationalError, DisconnectionError)
)


class DatabaseSessionManager:
    """Manages database session lifecycle with proper error handling"""
    
    def __init__(self):
        self._engine: Optional[AsyncEngine] = None
        self._sessionmaker: Optional[async_sessionmaker] = None
        
    async def init(self):
        """Initialize the database connection"""
        if self._engine is not None:
            return
            
        self._engine = async_engine
        self._sessionmaker = AsyncSessionLocal
        
        # Test connection
        try:
            async with self._engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
                log.info("Database connection established successfully")
        except Exception as e:
            log.error(f"Failed to connect to database: {e}")
            raise
            
    async def close(self):
        """Close database connection"""
        if self._engine is None:
            return
            
        await self._engine.dispose()
        self._engine = None
        self._sessionmaker = None
        log.info("Database connection closed")
        
    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """Provide a transactional scope with proper error handling"""
        if self._sessionmaker is None:
            await self.init()
            
        async with self._sessionmaker() as session:
            try:
                yield session
                await session.commit()
            except Exception as e:
                await session.rollback()
                log.error(f"Database session error: {e}")
                raise
            finally:
                await session.close()
                
    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[AsyncSession, None]:
        """Provide an explicit transaction scope"""
        async with self.session() as session:
            async with session.begin():
                yield session


# Global session manager instance
db_manager = DatabaseSessionManager()


# Dependency injection functions
def get_session():
    """Sync session dependency"""
    with SessionLocal() as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Async session dependency with proper lifecycle management"""
    async with db_manager.session() as session:
        yield session


# Database initialization and migration functions
async def init_db():
    """Initialize database with async support"""
    async with async_engine.begin() as conn:
        # In production, use Alembic migrations instead
        await conn.run_sync(SQLModel.metadata.create_all)
        log.info("Database tables created")


async def check_database_health() -> dict:
    """Check database health and connection status"""
    try:
        async with db_manager.session() as session:
            result = await session.execute("SELECT 1")
            result.scalar()
            
            # Get connection pool stats
            pool_status = async_engine.pool.status()
            
            return {
                "status": "healthy",
                "pool_size": async_engine.pool.size(),
                "checked_in_connections": async_engine.pool.checkedin(),
                "overflow": async_engine.pool.overflow(),
                "total": async_engine.pool.total,
                "pool_status": pool_status
            }
    except Exception as e:
        log.error(f"Database health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }


# Read/Write split support (future enhancement)
class ReadWriteSessionManager:
    """Manages read/write database splits for scaling"""
    
    def __init__(self, write_url: str, read_urls: list[str]):
        self.write_engine = create_async_engine(write_url, **db_config.async_engine_kwargs)
        self.read_engines = [
            create_async_engine(url, **db_config.async_engine_kwargs)
            for url in read_urls
        ]
        self._read_index = 0
        
    @asynccontextmanager
    async def read_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get a read-only session with round-robin load balancing"""
        engine = self.read_engines[self._read_index]
        self._read_index = (self._read_index + 1) % len(self.read_engines)
        
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            yield session
            
    @asynccontextmanager
    async def write_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get a write session"""
        async with async_sessionmaker(self.write_engine, expire_on_commit=False)() as session:
            yield session


# Export the enhanced functionality
__all__ = [
    "engine",
    "async_engine",
    "SessionLocal",
    "AsyncSessionLocal",
    "get_session",
    "get_async_session",
    "init_db",
    "check_database_health",
    "db_manager",
    "db_retry",
    "DatabaseSessionManager",
    "ReadWriteSessionManager"
]