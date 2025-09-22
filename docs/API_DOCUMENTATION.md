# LabelSquor API Documentation

## Overview

The LabelSquor API provides comprehensive product analysis with SQUOR scoring (Safety, Quality, Usability, Origin, Responsibility) for food products. The API includes both admin/crawler endpoints and consumer-facing endpoints optimized for UI applications.

## Base URL
```
http://localhost:8000/api/v1
```

## Authentication
Currently, the API does not require authentication for read operations. Admin operations may require authentication in the future.

---

## Consumer Endpoints

### 🔍 **Product Search**

**Endpoint:** `GET /products/search`

**Description:** Search and filter products with UI-friendly pagination and sorting

**Query Parameters:**
- `q` (string, optional): Search query (product name, brand, ingredients)
- `brand` (string, optional): Filter by brand name
- `category` (string, optional): Filter by category
- `min_score` (float, optional): Minimum SQUOR score (0-100)
- `max_score` (float, optional): Maximum SQUOR score (0-100)
- `grade` (string, optional): Filter by SQUOR grade (A, B, C, D, F)
- `sort_by` (string, default: "score"): Sort by score, name, brand, analyzed_at
- `sort_order` (string, default: "desc"): Sort order asc/desc
- `page` (int, default: 1): Page number
- `page_size` (int, default: 20, max: 100): Items per page

**Example Request:**
```bash
curl "http://localhost:8000/api/v1/products/search?q=millet&min_score=70&sort_by=score&page=1&page_size=10"
```

**Response:**
```json
{
  "products": [
    {
      "product_id": "uuid",
      "name": "Millet Namkeen Chilli Garlic - Chatpata",
      "brand": "Eat Better Co",
      "category": "snacks",
      "squor_score": 74.0,
      "squor_grade": "B",
      "key_claims": ["Roasted Not Fried", "No Palm Oil", "Zero Transfat"],
      "warnings": ["Contains Nuts"],
      "image_url": "https://example.com/image.jpg",
      "confidence": 0.8,
      "analyzed_at": "2025-09-22T15:19:49.561335"
    }
  ],
  "total_count": 1,
  "page": 1,
  "page_size": 10,
  "total_pages": 1,
  "query": "millet",
  "filters_applied": {
    "min_score": 70
  }
}
```

---

### 📄 **Product Details**

**Endpoint:** `GET /products/{product_id}`

**Description:** Get complete product details for product page

**Path Parameters:**
- `product_id` (UUID): Product identifier

**Example Request:**
```bash
curl "http://localhost:8000/api/v1/products/65de915b-b7e2-480a-9a72-de87895f2a29"
```

**Response:**
```json
{
  "product_id": "uuid",
  "name": "Millet Namkeen Chilli Garlic - Chatpata",
  "brand": "Eat Better Co",
  "category": "snacks",
  "squor_score": 74.0,
  "squor_grade": "B",
  "squor_components": {
    "safety": 100.0,
    "quality": 80.0,
    "usability": 80.0,
    "origin": 60.0,
    "responsibility": 40.0
  },
  "squor_explanations": {
    "safety": "Clear allergen disclosure ('Contains Nuts'), FSSAI license, and storage instructions are provided.",
    "quality": "Uses good quality millets and rice bran oil, is roasted not fried..."
  },
  "ingredients": [
    {
      "name": "Millets (Jowar, Bajra, Ragi)",
      "order": 0,
      "percentage": null
    }
  ],
  "nutrition": {
    "energy_kcal": 512.3,
    "protein_g": 15.4,
    "carbs_g": 52.7,
    "fat_g": 26.7,
    "sodium_mg": 512.7
  },
  "claims": [
    {
      "text": "Roasted Not Fried",
      "type": "quality",
      "verified": null
    }
  ],
  "warnings": [
    {
      "text": "Contains Nuts",
      "type": "allergen",
      "severity": "medium"
    }
  ],
  "verdict": {
    "overall_rating": 4,
    "recommendation": "This millet namkeen is a healthier snack option..."
  },
  "image_url": "https://example.com/image.jpg",
  "confidence": 0.8,
  "analyzed_at": "2025-09-22T15:19:49.561335",
  "analysis_cost": 0.0002,
  "model_used": "gemini-2.5-flash"
}
```

---

### 🎛️ **Filter Options**

**Endpoint:** `GET /products/filters/options`

**Description:** Get available filter options for UI filter components

**Example Request:**
```bash
curl "http://localhost:8000/api/v1/products/filters/options"
```

**Response:**
```json
{
  "brands": [
    {"name": "Eat Better Co", "count": 1},
    {"name": "Other Brand", "count": 5}
  ],
  "categories": [
    {"name": "snacks", "count": 1},
    {"name": "beverages", "count": 3}
  ],
  "score_ranges": [
    {"range": "90-100", "label": "Excellent (A)", "min": 90, "max": 100, "count": 0},
    {"range": "80-89", "label": "Good (B)", "min": 80, "max": 89, "count": 0},
    {"range": "70-79", "label": "Fair (C)", "min": 70, "max": 79, "count": 1}
  ]
}
```

---

## Admin/Crawler Endpoints

### 🕷️ **Category Crawl**

**Endpoint:** `POST /crawler/crawl/category`

**Description:** Crawl products from a specific category across retailers

**Request Body:**
```json
{
  "category": "snacks",
  "retailers": ["bigbasket"],
  "max_products": 10,
  "skip_existing": true,
  "consolidate_variants": true,
  "force_reanalysis": false
}
```

**Response:**
```json
{
  "session_id": "uuid",
  "status": "started",
  "started_at": "2025-09-22T15:19:49.561335",
  "products_found": 0,
  "products_analyzed": 0,
  "products_skipped": 0,
  "errors": [],
  "message": "Started crawling 'snacks' across 1 retailers"
}
```

---

### 📊 **Crawl Status**

**Endpoint:** `GET /crawler/status/{session_id}`

**Description:** Get the status of a crawl session

**Example Request:**
```bash
curl "http://localhost:8000/api/v1/crawler/status/session-uuid"
```

---

### 🔍 **Recent Products (Admin)**

**Endpoint:** `GET /crawler/products/recent`

**Description:** Get recently analyzed products with technical details

**Query Parameters:**
- `limit` (int, default: 10, max: 50): Number of products to return
- `skip_unanalyzed` (bool, default: true): Skip products without SQUOR scores
- `include_comprehensive` (bool, default: true): Include comprehensive AI data

---

## Data Models

### SQUOR Scoring

SQUOR is our proprietary scoring system that evaluates products across 5 dimensions:

- **S (Safety)**: 0-100 - Allergen disclosure, regulatory compliance, safety warnings
- **Q (Quality)**: 0-100 - Ingredient quality, processing methods, nutritional value
- **U (Usability)**: 0-100 - Package clarity, preparation ease, serving guidance
- **O (Origin)**: 0-100 - Sourcing transparency, country of origin, certifications
- **R (Responsibility)**: 0-100 - Environmental impact, social responsibility, marketing ethics

### Grade Mapping
- **A**: 90-100 (Excellent)
- **B**: 80-89 (Good)
- **C**: 70-79 (Fair)
- **D**: 60-69 (Poor)
- **F**: 0-59 (Very Poor)

---

## Error Responses

### 404 Not Found
```json
{
  "detail": "Product not found"
}
```

### 422 Validation Error
```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["query", "min_score"],
      "msg": "ensure this value is greater than or equal to 0"
    }
  ]
}
```

---

## Rate Limits

- **Consumer endpoints**: 100 requests/minute
- **Admin endpoints**: 10 requests/minute
- **AI analysis**: Costs tracked per request

---

## Development Notes

### Force Re-analysis
Use `force_reanalysis: true` in crawl requests to bypass duplicate detection and force fresh AI analysis.

### Image URLs
Currently using direct retailer image URLs. Migration to hosted images (Supabase) planned.

### Comprehensive Data
The API stores and exposes rich AI-extracted data including:
- Detailed ingredient lists with percentages
- Complete nutrition facts
- Marketing claims with verification status
- Warnings and allergen information
- AI verdict and recommendations
- Analysis metadata (cost, confidence, model used)

---

## API Health

**Endpoint:** `GET /health`

**Description:** Check API health and database connectivity

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-09-22T15:19:49.561335",
  "database": "connected",
  "version": "1.0.0"
}
```

---

*Last updated: September 22, 2025*
*This documentation should be updated whenever API changes are made.*
