# LabelSquor API Project Structure

## Overview
Clean, maintainable structure for the LabelSquor API with proper separation of concerns.

## Directory Structure

```
labelsquor-api/
├── app/                          # Main application code
│   ├── api/                      # API layer
│   │   ├── deps.py              # Dependency injection
│   │   └── v1/                  # API v1 endpoints
│   │       ├── crawler.py       # Admin crawler endpoints
│   │       ├── products.py      # Consumer product endpoints
│   │       ├── health.py        # Health checks
│   │       └── ...              # Other endpoints
│   ├── core/                     # Core functionality
│   │   ├── config.py            # Configuration
│   │   ├── database.py          # Database setup
│   │   ├── logging.py           # Logging configuration
│   │   └── ...
│   ├── models/                   # Database models
│   │   ├── product.py           # Product models
│   │   ├── ai_analysis.py       # AI analysis models
│   │   ├── scoring.py           # SQUOR scoring models
│   │   └── ...
│   ├── repositories/             # Data access layer
│   │   ├── product.py           # Product repository
│   │   └── ...
│   ├── services/                 # Business logic
│   │   ├── ai_pipeline_service.py     # AI analysis pipeline
│   │   ├── ai_analysis_service.py     # Comprehensive data storage
│   │   ├── product_consolidator.py    # Product consolidation
│   │   └── ...
│   ├── utils/                    # Utilities
│   │   ├── product_identification.py  # EAN/product ID utilities
│   │   ├── content_hash.py            # Content hashing
│   │   └── ...
│   └── main.py                   # FastAPI application
├── tests/                        # Test suite
│   ├── unit/                     # Unit tests
│   │   ├── api/                  # API unit tests
│   │   ├── services/             # Service unit tests
│   │   ├── repositories/         # Repository unit tests
│   │   └── utils/                # Utility unit tests
│   ├── integration/              # Integration tests
│   │   ├── api/                  # API integration tests
│   │   └── services/             # Service integration tests
│   └── e2e/                      # End-to-end tests
├── docs/                         # Documentation
│   ├── API_DOCUMENTATION.md     # Complete API docs
│   └── ...                      # Other documentation
├── scripts/                      # Utility scripts
│   ├── reset_database.py        # Database reset
│   ├── clear_database.py        # Clear data
│   └── ...
├── alembic/                      # Database migrations
├── requirements/                 # Dependencies
│   ├── base.txt                 # Core dependencies
│   ├── dev.txt                  # Development dependencies
│   └── ...
├── configs/                      # Configuration files
├── data/                         # Seed data
├── Makefile                      # Build commands
├── pyproject.toml               # Project metadata
└── README.md                    # Project overview
```

## Key Principles

### 1. **Separation of Concerns**
- **API Layer**: FastAPI endpoints and request/response models
- **Service Layer**: Business logic and orchestration
- **Repository Layer**: Data access and persistence
- **Models**: Database schema and domain models

### 2. **Product Identification**
- **EAN Codes**: Primary identification (globally unique)
- **Retailer IDs**: Secondary identification (extracted from URLs)
- **Content Hash**: Fallback identification (brand + name + pack_size)

### 3. **AI Analysis Pipeline**
- **Smart Duplicate Detection**: Avoids redundant analysis
- **Comprehensive Data Storage**: Ingredients, nutrition, claims, warnings
- **Cost Optimization**: Tracks usage and prevents unnecessary calls

### 4. **Consumer-Friendly APIs**
- **Paginated Search**: `/api/v1/products/search`
- **Product Details**: `/api/v1/products/{id}`
- **Filter Options**: `/api/v1/products/filters/options`

### 5. **Test Organization**
- **Unit Tests**: Individual component testing
- **Integration Tests**: Component interaction testing
- **E2E Tests**: Full workflow testing

## Development Workflow

1. **Database Changes**: Use Alembic migrations
2. **API Changes**: Update `docs/API_DOCUMENTATION.md`
3. **New Features**: Add tests in appropriate test directories
4. **Dependencies**: Add to appropriate `requirements/*.txt` file

## Production Readiness

- ✅ **Proper Error Handling**: Quota exhaustion, validation errors
- ✅ **Comprehensive Logging**: Structured logging with correlation IDs
- ✅ **Database Migrations**: Versioned schema changes
- ✅ **API Documentation**: Complete endpoint documentation
- ✅ **Test Coverage**: Unit, integration, and E2E tests
- ✅ **Configuration Management**: Environment-based settings

---

*This structure ensures maintainability, scalability, and proper separation of concerns for the LabelSquor API.*
