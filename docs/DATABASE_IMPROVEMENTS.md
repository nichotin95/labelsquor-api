# Database Management Improvements

## Overview

We've significantly improved the database management system with better connection handling, migration support, and production-ready features.

## Key Improvements

### 1. Enhanced Connection Management

**File**: `app/core/database.py`

- **Connection Pooling**: Properly configured with size limits and recycling
- **Retry Logic**: Automatic retry with exponential backoff for transient failures
- **Health Checks**: Connection health monitoring and pool statistics
- **Async Context Managers**: Proper session lifecycle management
- **Read/Write Split Support**: Foundation for scaling with read replicas

```python
# Example usage
async with db_manager.session() as session:
    # Automatic commit on success, rollback on error
    result = await session.execute(query)
```

### 2. Migration System with Alembic

**Files**: 
- `alembic.ini` - Configuration
- `alembic/env.py` - Async migration support
- `scripts/migrate.py` - Migration management CLI

**Usage**:
```bash
# Create a new migration
python scripts/migrate.py create "Add user table"

# Apply migrations
python scripts/migrate.py upgrade

# Rollback one migration
python scripts/migrate.py downgrade

# View current revision
python scripts/migrate.py current
```

### 3. Configuration Improvements

- **Environment-based settings**: All DB settings from environment
- **Connection resilience**: Pool pre-ping, connection recycling
- **Timeout management**: Configurable connection and pool timeouts
- **Application identification**: Sets application_name for monitoring

### 4. Database Setup Script

**File**: `scripts/setup_database.py`

Enhanced setup script that:
- Creates database if it doesn't exist
- Installs PostgreSQL extensions
- Runs migrations automatically
- Creates initial data (categories, retailers)
- Verifies setup completion

```bash
# Run complete database setup
python scripts/setup_database.py
```

## Production Features

### Connection Pool Configuration

```python
# Optimized for production
pool_size = 20          # Base connections
max_overflow = 0        # No overflow (predictable resource usage)
pool_recycle = 3600     # Recycle connections hourly
pool_timeout = 30       # Wait up to 30s for connection
pool_pre_ping = True    # Test connections before use
```

### Health Monitoring

```python
# Check database health
health = await check_database_health()
# Returns: {
#   "status": "healthy",
#   "pool_size": 20,
#   "checked_in_connections": 18,
#   "overflow": 0,
#   "total": 20
# }
```

### Error Handling

- Automatic retry for operational errors
- Proper transaction rollback
- Detailed error logging
- Connection cleanup on failure

## Migration Strategy

### From Raw SQL to Alembic

1. **Initial Migration**: Import existing SQL schema
   ```bash
   alembic revision --autogenerate -m "Initial schema import"
   ```

2. **Future Changes**: Use migrations for all schema changes
   ```bash
   python scripts/migrate.py create "Add email column to user"
   ```

3. **Version Control**: All migrations tracked in git

### Best Practices

1. **Always review auto-generated migrations** before applying
2. **Test migrations** on a staging database first
3. **Backup production** before applying migrations
4. **Use transactions** for data migrations

## Performance Optimizations

1. **Connection Pooling**: Reuse connections instead of creating new ones
2. **Prepared Statements**: SQLAlchemy uses prepared statements automatically
3. **Index Management**: Migrations include index definitions
4. **Query Optimization**: Use explain plans for slow queries

## Monitoring & Observability

### Logging

- Connection establishment/closure
- Pool statistics
- Query execution times (when debug enabled)
- Migration execution

### Metrics to Track

- Pool utilization
- Connection wait times
- Transaction duration
- Migration execution time

## Security Enhancements

1. **No hardcoded credentials**: All from environment
2. **Encrypted connections**: SSL/TLS support
3. **Least privilege**: App user with minimal permissions
4. **SQL injection protection**: Parameterized queries only

## Scaling Considerations

### Read Replicas

```python
# Future implementation ready
rw_manager = ReadWriteSessionManager(
    write_url="postgresql://master...",
    read_urls=["postgresql://replica1...", "postgresql://replica2..."]
)

# Use read replica for queries
async with rw_manager.read_session() as session:
    data = await session.execute(select_query)

# Use master for writes
async with rw_manager.write_session() as session:
    await session.execute(insert_query)
```

### Connection Limits

- Configure based on available PostgreSQL connections
- Formula: `pool_size * num_workers < max_connections * 0.8`
- Monitor connection usage and adjust

## Troubleshooting

### Common Issues

1. **"Too many connections"**
   - Reduce pool_size or number of workers
   - Check for connection leaks

2. **"Connection timeout"**
   - Increase connect_timeout
   - Check network connectivity
   - Verify PostgreSQL is accepting connections

3. **"Migration failed"**
   - Check migration SQL for errors
   - Ensure database user has DDL permissions
   - Review migration dependencies

## Future Enhancements

1. **Query Result Caching**: Integration with Redis
2. **Query Performance Monitoring**: Slow query logging
3. **Automatic Failover**: Multi-master support
4. **Connection Encryption**: Enforced TLS 1.3+
5. **Audit Logging**: Track all data modifications
