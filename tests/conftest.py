"""
Test configuration and fixtures
"""

import asyncio
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlmodel import SQLModel

from app.main import app
from app.core.config import settings
from app.core.database import get_session


# Test database URL (use a separate test database)
TEST_DATABASE_URL = str(settings.database_url).replace("/postgres", "/postgres_test")

# Test engine
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    pool_pre_ping=True
)

TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    expire_on_commit=False
)


@pytest_asyncio.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def setup_test_db():
    """Set up test database"""
    # Create all tables
    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    
    yield
    
    # Clean up
    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session(setup_test_db):
    """Create a test database session"""
    async with TestSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_session):
    """Create test client with database override"""
    
    async def get_test_session():
        yield db_session
    
    app.dependency_overrides[get_session] = get_test_session
    
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear()


@pytest.fixture
def sample_category_mapping():
    """Sample category mapping data"""
    return {
        "retailer": "bigbasket",
        "internal_category": "snacks",
        "retailer_category_name": "Snacks & Branded Foods",
        "retailer_category_path": "/pc/Snacks-Branded-Foods/",
        "level": 1,
        "is_active": True
    }


@pytest.fixture
def sample_crawler_request():
    """Sample crawler request data"""
    return {
        "category": "snacks",
        "retailers": ["bigbasket"],
        "max_products": 2,
        "skip_existing": True,
        "consolidate_variants": True
    }
