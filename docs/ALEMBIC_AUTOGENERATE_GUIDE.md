# Alembic Auto-generate Guide

## Overview

This guide explains how to use Alembic's auto-generate feature to automatically create migrations when you change SQLModel definitions.

## Workflow for Model Changes

### 1. Make Changes to SQLModel

Edit your model files in `app/models/`:

```python
# Example: Adding a new field to Product model
class Product(SQLModel, table=True):
    # ... existing fields ...
    
    # New field
    is_featured: bool = Field(default=False, description="Featured product flag")
    featured_at: Optional[datetime] = Field(default=None, description="When product was featured")
```

### 2. Generate Migration Automatically

```bash
# Use the make command
make db-generate-migration
# Enter a descriptive message like: "Add featured fields to product"

# Or use Alembic directly
alembic revision --autogenerate -m "Add featured fields to product"
```

### 3. Review Generated Migration

Always review the generated migration file in `alembic/versions/`:

```python
def upgrade() -> None:
    # Alembic generated this
    op.add_column('product', sa.Column('is_featured', sa.Boolean(), nullable=False))
    op.add_column('product', sa.Column('featured_at', sa.DateTime(), nullable=True))

def downgrade() -> None:
    # Alembic generated this
    op.drop_column('product', 'featured_at')
    op.drop_column('product', 'is_featured')
```

### 4. Apply Migration

```bash
# Apply the migration
make db-migrate

# Or check status first
make db-current
```

## Common Scenarios

### Adding a New Model

1. Create the model in `app/models/`:
```python
class ProductReview(SQLModel, table=True):
    __tablename__ = "product_review"
    
    review_id: UUID = Field(default_factory=uuid4, primary_key=True)
    product_id: UUID = Field(foreign_key="product.product_id")
    rating: int = Field(ge=1, le=5)
    comment: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

2. Import it in `app/models/__init__.py`

3. Generate migration:
```bash
make db-generate-migration
# Message: "Add product review model"
```

### Adding an Index

```python
class Product(SQLModel, table=True):
    # ... fields ...
    
    class Config:
        # Add index on created_at for sorting
        indexes = [
            Index("idx_product_created_at", "created_at"),
        ]
```

### Adding a Relationship

```python
class Product(SQLModel, table=True):
    # ... fields ...
    
    # Add relationship
    reviews: List["ProductReview"] = Relationship(back_populates="product")
```

## What Alembic Auto-detects

✅ **Detects automatically:**
- Table additions/removals
- Column additions/removals
- Column type changes
- Nullable changes
- Index additions/removals
- Foreign key changes
- Unique constraint changes

⚠️ **May need manual adjustment:**
- Column renames (detected as drop + add)
- Table renames
- Complex type changes
- Custom constraints
- Enum type changes

❌ **Not detected:**
- Data migrations
- Stored procedures
- Triggers
- Views (unless using special configuration)

## Best Practices

### 1. Always Review Generated Migrations

```bash
# After generating, check the file
cat alembic/versions/latest_migration.py
```

### 2. Test Migrations Locally

```bash
# Test upgrade
make db-migrate

# Test downgrade
alembic downgrade -1

# Test upgrade again
alembic upgrade head
```

### 3. Handle Column Renames

If renaming a column, edit the generated migration:

```python
def upgrade():
    # Instead of drop + add
    # op.drop_column('product', 'old_name')
    # op.add_column('product', sa.Column('new_name', ...))
    
    # Use rename
    op.alter_column('product', 'old_name', new_column_name='new_name')
```

### 4. Include Data Migrations When Needed

```python
def upgrade():
    # Schema change
    op.add_column('product', sa.Column('slug', sa.String(), nullable=True))
    
    # Data migration
    op.execute("""
        UPDATE product 
        SET slug = LOWER(REPLACE(name, ' ', '-'))
        WHERE slug IS NULL
    """)
    
    # Make non-nullable after data migration
    op.alter_column('product', 'slug', nullable=False)
```

## Troubleshooting

### Issue: Migration Detects Too Many Changes

This happens when database is out of sync with models.

**Solution:**
```bash
# Option 1: Reset database (development only)
make db-reset-force

# Option 2: Create a baseline
alembic stamp head  # Mark current schema as up-to-date
```

### Issue: Import Errors in Migration

**Solution:** Ensure all models are imported in `app/models/__init__.py`

### Issue: Circular Dependencies

**Solution:** Use string references for relationships:
```python
# Instead of
reviews: List[ProductReview] = Relationship(...)

# Use
reviews: List["ProductReview"] = Relationship(...)
```

## Complete Example

Let's add a feature for product variants:

1. **Create new model:**
```python
# app/models/product_variant.py
class ProductVariant(SQLModel, table=True):
    __tablename__ = "product_variant"
    
    variant_id: UUID = Field(default_factory=uuid4, primary_key=True)
    product_id: UUID = Field(foreign_key="product.product_id")
    sku: str = Field(index=True)
    name: str  # e.g., "500g", "1kg"
    price: Decimal = Field(decimal_places=2)
    stock_quantity: int = Field(default=0)
    is_default: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationship
    product: "Product" = Relationship(back_populates="variants")
```

2. **Update Product model:**
```python
# app/models/product.py
class Product(SQLModel, table=True):
    # ... existing fields ...
    
    # Add relationship
    variants: List["ProductVariant"] = Relationship(back_populates="product")
```

3. **Generate migration:**
```bash
make db-generate-migration
# Message: "Add product variants support"
```

4. **Review and apply:**
```bash
# Review the generated file
cat alembic/versions/*product_variants*.py

# Apply
make db-migrate
```

## Using API Instead of Make Commands

For crawling, use the API examples:

```bash
# Start the API server
make run

# In another terminal, use the API client
python examples/api_crawler_example.py crawl

# Or use curl
curl -X POST http://localhost:8000/api/v1/crawler/discover \
  -H "Content-Type: application/json" \
  -d '{
    "retailer_slug": "bigbasket",
    "category": "snacks",
    "max_products": 2
  }'
```

## Summary

1. **Change models** → SQLModel definitions
2. **Generate migration** → `make db-generate-migration`
3. **Review changes** → Check generated file
4. **Apply migration** → `make db-migrate`
5. **Use API** → For all operations instead of make commands
