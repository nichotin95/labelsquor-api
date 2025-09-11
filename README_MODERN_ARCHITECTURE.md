# 🚀 LabelSquor API - Modern Architecture

## 🏗️ Architecture Overview

This is a production-ready FastAPI application built with modern Python best practices and cutting-edge libraries.

### 🎯 Key Design Principles

1. **Clean Architecture** - Separation of concerns with distinct layers
2. **Dependency Injection** - Using FastAPI's powerful DI system
3. **Async First** - Full async/await support for high performance
4. **Type Safety** - Pydantic V2 + SQLModel for runtime validation
5. **Observability** - Structured logging, metrics, and tracing
6. **Scalability** - Designed for horizontal scaling

## 📁 Project Structure

```
app/
├── api/
│   ├── deps.py          # Dependency injection
│   └── v1/              # API version 1
│       ├── brands.py    # Brand endpoints
│       ├── products.py  # Product endpoints
│       └── ...
├── core/
│   ├── config.py        # Pydantic settings
│   ├── database.py      # Database connections
│   ├── logging.py       # Structured logging
│   ├── cache.py         # Advanced caching
│   └── exceptions.py    # Custom exceptions
├── models/              # SQLModel database models
├── schemas/             # Pydantic API schemas
├── repositories/        # Data access layer
├── services/           # Business logic layer
├── utils/              # Utility functions
└── main.py            # FastAPI application
```

## 🚀 Modern Features

### 1. **Advanced Caching**
- Redis with in-memory fallback
- Decorator-based caching with TTL
- Cache invalidation patterns
- Fluent cache key builder

```python
@cached(ttl=300, key_prefix="user")
async def get_user(user_id: int):
    return await db.get_user(user_id)
```

### 2. **Structured Logging**
- JSON structured logs with Loguru
- Request correlation IDs
- Performance monitoring
- Automatic exception tracking

```python
log.info("User created", user_id=user.id, email=user.email)
```

### 3. **Repository Pattern**
- Generic base repository with CRUD
- Type-safe operations
- Bulk operations support
- Soft delete capability

```python
class BrandRepository(BaseRepository[Brand, BrandCreate, BrandUpdate]):
    async def search(self, query: str) -> List[Brand]:
        # Custom search logic
```

### 4. **Service Layer**
- Business logic separation
- Transaction management
- Cross-cutting concerns
- Cache integration

### 5. **Advanced Middleware**
- Request ID tracking
- Performance monitoring
- Security headers
- Structured access logs

### 6. **API Features**
- Rate limiting with SlowAPI
- Response caching
- Background tasks
- Webhook support
- GraphQL integration (optional)

### 7. **Observability**
- OpenTelemetry integration
- Prometheus metrics
- Sentry error tracking
- Custom health checks

### 8. **Security**
- JWT authentication
- CORS configuration
- Security headers
- Rate limiting per user/IP

## 🛠️ Cool Libraries Used

### Core
- **FastAPI** (0.109.0) - Modern web framework
- **Pydantic V2** (2.5.3) - Data validation
- **SQLModel** - SQL databases with Python
- **Asyncpg** - Fast PostgreSQL driver

### Performance
- **ORjson** - Fastest JSON serialization
- **aiocache** - Async caching with Redis
- **msgpack** - Binary serialization

### Observability
- **Loguru** - Better logging
- **OpenTelemetry** - Distributed tracing
- **Prometheus** - Metrics
- **Sentry** - Error tracking

### Development
- **Rich** - Beautiful terminal output
- **Typer** - CLI applications
- **Hypothesis** - Property-based testing
- **Factory Boy** - Test data generation

### Optional Features
- **Strawberry GraphQL** - Modern GraphQL
- **Dramatiq** - Task queue (Celery alternative)
- **Celery** - Traditional task queue

## 🚀 Getting Started

### 1. Environment Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt

# Copy environment variables
cp .env.example .env
# Edit .env with your settings
```

### 2. Database Setup

```bash
# Run migrations
alembic upgrade head

# Or use Flyway for production
flyway migrate
```

### 3. Run Development Server

```bash
# With hot reload
uvicorn app.main:app --reload

# Or using the CLI
python -m app.cli serve --dev
```

### 4. Run Production Server

```bash
# With Gunicorn
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker

# Or with Uvicorn directly
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## 📝 API Examples

### Create a Brand
```bash
curl -X POST http://localhost:8000/api/v1/brands \
  -H "Content-Type: application/json" \
  -d '{"name": "Amul", "country": "IN"}'
```

### Search Products with Caching
```bash
curl "http://localhost:8000/api/v1/products?q=milk&category=dairy"
# Response includes X-Cache: HIT/MISS header
```

### Health Check
```bash
curl http://localhost:8000/api/v1/health
# Returns database status, cache status, etc.
```

## 🧪 Testing

```bash
# Run all tests
pytest

# With coverage
pytest --cov=app --cov-report=html

# Run specific test
pytest tests/test_brands.py::test_create_brand
```

## 📊 Performance Optimizations

1. **Connection Pooling** - Async PostgreSQL with connection pools
2. **Response Caching** - Redis caching for GET endpoints
3. **Bulk Operations** - Batch inserts/updates
4. **Lazy Loading** - Relationships loaded on demand
5. **Query Optimization** - Indexed columns, optimized queries

## 🔐 Security Best Practices

1. **Input Validation** - Pydantic models validate all inputs
2. **SQL Injection Protection** - Parameterized queries only
3. **Authentication** - JWT with refresh tokens
4. **Rate Limiting** - Per-user and per-IP limits
5. **CORS** - Configurable allowed origins
6. **Security Headers** - XSS, CSRF protection

## 🚢 Deployment

### Docker
```dockerfile
FROM python:3.11-slim
# Multi-stage build for smaller images
```

### Kubernetes
```yaml
apiVersion: apps/v1
kind: Deployment
# Horizontal pod autoscaling
```

### Environment Variables
- `DATABASE_URL` - PostgreSQL connection
- `REDIS_URL` - Redis connection
- `SENTRY_DSN` - Error tracking
- `SECRET_KEY` - JWT signing key

## 📚 Additional Resources

- [FastAPI Best Practices](https://github.com/zhanymkanov/fastapi-best-practices)
- [Python Type Hints](https://docs.python.org/3/library/typing.html)
- [Async Python](https://docs.python.org/3/library/asyncio.html)
- [SQLModel Tutorial](https://sqlmodel.tiangolo.com/)

## 🤝 Contributing

1. Follow PEP 8 with Black formatting
2. Add type hints to all functions
3. Write tests for new features
4. Update documentation

---

Built with ❤️ using modern Python
