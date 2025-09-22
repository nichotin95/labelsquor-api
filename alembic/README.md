# Alembic Database Migrations

This directory contains database migration files managed by Alembic.

## Quick Start

### Create a new migration
```bash
python scripts/migrate.py create "Add user table"
```

### Apply all migrations
```bash
python scripts/migrate.py upgrade
```

### Rollback one migration
```bash
python scripts/migrate.py downgrade
```

### Check current version
```bash
python scripts/migrate.py current
```

### View history
```bash
python scripts/migrate.py history
```

## First Time Setup

If you have existing tables created by SQLModel, you can create an initial migration:

```bash
# 1. Ensure database is up to date with current models
python scripts/setup_database.py

# 2. Generate initial migration
alembic revision --autogenerate -m "Initial schema"

# 3. Review and edit the generated migration
# Remove any create_table statements for tables that already exist

# 4. Mark as applied without running
alembic stamp head
```

## Migration Best Practices

1. **Always review auto-generated migrations** - Alembic may miss some changes
2. **Test migrations on a copy** of production data before applying
3. **Include both upgrade and downgrade** operations
4. **Use transactions** for data migrations
5. **Keep migrations small and focused** - one logical change per migration

## Common Operations

### Add a column
```python
def upgrade():
    op.add_column('user', sa.Column('email', sa.String(255)))

def downgrade():
    op.drop_column('user', 'email')
```

### Create an index
```python
def upgrade():
    op.create_index('ix_user_email', 'user', ['email'])

def downgrade():
    op.drop_index('ix_user_email', 'user')
```

### Modify column type
```python
def upgrade():
    op.alter_column('product', 'price',
                    type_=sa.Numeric(10, 2),
                    existing_type=sa.Integer)
```

## Troubleshooting

### "Can't locate revision identified by 'xxx'"
The database is out of sync. Check current version:
```bash
python scripts/migrate.py current
```

### "Target database is not up to date"
Run pending migrations:
```bash
python scripts/migrate.py upgrade
```

### Migration fails
1. Check the error message
2. Manually fix the database if needed
3. Mark the migration as applied: `alembic stamp <revision>`
