# Product Discovery Strategies for LabelSquor Crawlers

## The Challenge

Modern e-commerce sites like BigBasket, Blinkit, and Zepto use various techniques that make product discovery challenging:
- Dynamic JavaScript loading
- API-driven content
- Lazy loading on scroll
- Protected/authenticated APIs
- Anti-bot measures

## Discovery Strategies

### 1. 🗺️ Sitemap Mining
**Most reliable for large-scale discovery**

```python
# Check these URLs
https://www.bigbasket.com/sitemap.xml
https://www.bigbasket.com/sitemap-index.xml
https://www.bigbasket.com/product-sitemap.xml
```

**Pros**: Official, comprehensive, bot-friendly
**Cons**: May not include all products, can be outdated

### 2. 🔍 Search Queries
**Use popular brand and product names**

```python
search_terms = [
    # Popular brands
    'maggi', 'lays', 'kurkure', 'coca cola', 'pepsi',
    'amul', 'britannia', 'parle', 'haldiram', 'nestle',
    
    # Categories
    'chips', 'biscuits', 'noodles', 'chocolate', 'milk',
    
    # Specific products
    'maggi masala', 'lays magic masala', 'amul butter'
]
```

### 3. 📂 Category Traversal
**Systematic exploration of category pages**

```
Home → Categories → Subcategories → Products
```

Example flow:
```
/pc/snacks-branded-foods/
  → /pc/snacks-branded-foods/chips-crisps/
    → /pd/12345/lays-magic-masala/
```

### 4. 🎭 JavaScript Rendering (Playwright)
**For sites that load products dynamically**

```python
# Use Scrapy-Playwright to:
1. Load the page
2. Wait for products to appear
3. Scroll to trigger lazy loading
4. Click "Load More" buttons
5. Extract product URLs
```

### 5. 🔌 API Discovery
**Find hidden APIs through browser DevTools**

Common patterns:
```
/api/v1/products/search
/api/v2/category/products
/ps/v1/products/list
/graphql (with product queries)
```

### 6. 🏪 Seller/Brand Pages
**Many sites have dedicated brand pages**

```
/brands/nestle/
/seller/haldiram/
/store/amul-official/
```

### 7. 📊 Trending/Popular Lists
**High-value products**

```
/trending-products/
/bestsellers/
/new-arrivals/
/deals-of-the-day/
```

## Implementation Priority

### Phase 1: Quick Wins (No JS Required)
1. **Sitemap Parser** ✅
2. **Search API Discovery** ✅
3. **Category URL Patterns** ✅

### Phase 2: JavaScript Rendering
1. **Playwright Integration** ✅
2. **Scroll & Load More** ✅
3. **Dynamic Content Extraction** ✅

### Phase 3: Scale & Optimize
1. **Distributed Crawling** (Scrapy-Redis)
2. **Proxy Rotation**
3. **Request Caching**

## Usage Examples

### Run Discovery Spider
```bash
# Discover product URLs from multiple sources
scrapy crawl bigbasket_discovery -o discovered_products.json

# Use Playwright for JavaScript sites
scrapy crawl bigbasket_playwright -L INFO
```

### Deploy to Cloud
```bash
# GitHub Actions (FREE)
gh workflow run crawl-products -f spider=bigbasket_discovery

# Scrapy Cloud
shub deploy
shub schedule bigbasket_discovery
```

## Anti-Bot Measures

### Common Protections
- Rate limiting → Use delays and AutoThrottle
- User-Agent checking → Rotate user agents
- Cookie validation → Maintain session cookies
- Captchas → Use proxy services or manual solving

### Best Practices
1. **Respect robots.txt** (always)
2. **Add delays between requests** (1-2 seconds)
3. **Rotate user agents**
4. **Use residential proxies** (if needed)
5. **Implement exponential backoff**

## Monitoring & Maintenance

### Track Success Metrics
- Products discovered per day
- Success rate per strategy
- New products vs existing
- Failed requests

### Adapt to Changes
- Monitor for HTML structure changes
- Update selectors regularly
- Track API endpoint changes
- Maintain multiple fallback strategies

## Database Integration

Once URLs are discovered, they're sent to the processing queue:

```python
# In pipeline.py
def process_item(self, item, spider):
    if item['type'] == 'product':
        # Send to LabelSquor API
        response = self.client.post(
            '/api/v1/crawler/products',
            json={
                'url': item['url'],
                'discovery_method': item['discovery_method'],
                'metadata': item
            }
        )
```

## Next Steps

1. **Test each discovery method** locally
2. **Deploy to GitHub Actions** for daily runs
3. **Monitor discovery rates**
4. **Add more retailers** (Blinkit, Zepto, Amazon)
5. **Implement deduplication**
