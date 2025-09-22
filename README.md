# LabelSquor API

🏷️ **AI-Powered Product Analysis API**

The LabelSquor API provides comprehensive food product analysis with SQUOR scoring (Safety, Quality, Usability, Origin, Responsibility). Built with FastAPI, PostgreSQL, and Google Gemini AI.

## ✨ Features

- 🤖 **AI-Powered Analysis**: Comprehensive product analysis using Google Gemini
- 🏷️ **SQUOR Scoring**: 5-dimensional product scoring with explanations
- 🔍 **Smart Search**: Paginated, filterable product search
- 📊 **Rich Data**: Ingredients, nutrition, claims, warnings, and recommendations
- 🚀 **EAN-Based Identification**: Proper product deduplication across retailers
- 💰 **Cost Optimization**: Smart duplicate detection to avoid redundant analysis
- 📱 **Consumer-Ready APIs**: UI-friendly endpoints for frontend applications

## 🚀 Quick Start

```bash
# Setup
make setup-dev
make db-reset

# Start server
make serve

# Test the API
curl "http://localhost:8000/api/v1/products/search"
```

## 📚 Documentation

- **[API Documentation](docs/API_DOCUMENTATION.md)** - Complete API reference
- **[Project Structure](PROJECT_STRUCTURE.md)** - Codebase organization
- **[Database Setup](docs/DATABASE_SETUP_COMPLETE.md)** - Database configuration

## 🏗️ Architecture

- **FastAPI** - Modern async Python web framework
- **PostgreSQL** - Robust relational database
- **SQLModel** - Type-safe ORM with Pydantic integration
- **Alembic** - Database migration management
- **Google Gemini** - AI analysis with image understanding
- **Scrapy** - Web scraping for product discovery

## 🧪 Testing

```bash
# Run all tests
pytest

# Run specific test categories
pytest tests/unit/
pytest tests/integration/
pytest tests/e2e/
```

## 📊 Current Status

- ✅ **13+ Products** analyzed and scored
- ✅ **Multiple Retailers** supported (BigBasket, Blinkit, Zepto)
- ✅ **Comprehensive AI Data** stored and exposed
- ✅ **Consumer APIs** ready for frontend integration
- ✅ **Production Ready** with proper error handling and logging

## 🛠️ Development

### Database Operations
```bash
make db-reset          # Reset database with fresh schema
make db-migrate        # Run pending migrations
make db-clear          # Clear data only
```

### API Server
```bash
make serve            # Development server with reload
make serve-prod       # Production server
```

### Crawling & Analysis
```bash
# Crawl products (via API)
curl -X POST "http://localhost:8000/api/v1/crawler/crawl/category" \
  -H "Content-Type: application/json" \
  -d '{"category": "snacks", "retailers": ["bigbasket"], "max_products": 5}'

# Force re-analysis
curl -X POST "http://localhost:8000/api/v1/crawler/crawl/category" \
  -H "Content-Type: application/json" \
  -d '{"category": "snacks", "force_reanalysis": true}'
```

## 🔧 Configuration

Set environment variables:
```bash
export DATABASE_URL="postgresql://user:pass@localhost/labelsquor"
export GOOGLE_API_KEY="your-gemini-api-key"
export SUPABASE_URL="your-supabase-url"
export SUPABASE_ANON_KEY="your-supabase-key"
```

## 🎯 API Endpoints

### Consumer Endpoints
- `GET /api/v1/products/search` - Search and filter products
- `GET /api/v1/products/{id}` - Get product details
- `GET /api/v1/products/filters/options` - Get filter options

### Admin Endpoints  
- `POST /api/v1/crawler/crawl/category` - Crawl product category
- `GET /api/v1/crawler/status/{session_id}` - Check crawl status
- `GET /api/v1/crawler/products/recent` - Recent analyses

## 📈 SQUOR Scoring

Our proprietary 5-dimensional scoring system:

- **S (Safety)**: 0-100 - Allergen disclosure, regulatory compliance
- **Q (Quality)**: 0-100 - Ingredient quality, processing methods  
- **U (Usability)**: 0-100 - Package clarity, preparation ease
- **O (Origin)**: 0-100 - Sourcing transparency, certifications
- **R (Responsibility)**: 0-100 - Environmental impact, social responsibility

## 🏆 Grade Mapping
- **A**: 90-100 (Excellent)
- **B**: 80-89 (Good)  
- **C**: 70-79 (Fair)
- **D**: 60-69 (Poor)
- **F**: 0-59 (Very Poor)

---

**Built with ❤️ for transparent food labeling**