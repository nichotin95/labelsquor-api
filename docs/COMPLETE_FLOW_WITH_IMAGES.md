# Complete Product Analysis Flow with Image Hosting

## Overview

This document describes the complete flow from crawling to displaying products with hosted images.

## Flow Diagram

```
1. Crawler discovers product
   ↓
2. Extract basic info + image URLs
   ↓
3. Queue for AI analysis
   ↓
4. Gemini analyzes product:
   - Extracts ingredients, nutrition, etc.
   - Selects best image for display
   ↓
5. Upload selected image to Supabase
   ↓
6. Save hosted URL to database
   ↓
7. Frontend displays hosted image
```

## Detailed Steps

### 1. Product Discovery

```bash
# Via API
curl -X POST http://localhost:8000/api/v1/crawler/discover \
  -H "Content-Type: application/json" \
  -d '{
    "retailer_slug": "bigbasket",
    "category": "snacks",
    "max_products": 2
  }'
```

### 2. AI Analysis with Image Selection

The Gemini prompt now includes image selection:

```json
{
  "product": {"name": "Lays Classic Salted", "brand": "Lays"},
  "ingredients": ["Potatoes", "Edible Vegetable Oil", "Salt"],
  "nutrition": {"energy": 544, "fat": 35.6, ...},
  "scores": {"safety": 75, "quality": 70, ...},
  "best_image": {
    "index": 1,
    "reason": "Clear front view showing product name and branding"
  }
}
```

### 3. Image Upload Process

```python
# In AI pipeline service
if best_image_index < len(image_urls):
    best_image_url = image_urls[best_image_index]
    
    # Upload to Supabase Storage
    hosted_url = await image_hosting_service.upload_image_from_url(
        image_url=best_image_url,
        product_id=str(product_id),
        image_type="primary"
    )
    
    # Update product
    product.primary_image_url = hosted_url
    product.primary_image_source = "bigbasket"
```

### 4. Image Optimization

Before uploading, images are:
- Resized to max 800x800 pixels
- Converted to JPEG for photos, PNG for graphics
- Compressed to reduce file size
- Cached for 1 year

### 5. API Response

```json
GET /api/v1/products/123

{
  "product_id": "123",
  "name": "Lays Classic Salted",
  "brand": {
    "brand_id": "456",
    "name": "Lays"
  },
  "primary_image_url": "https://snjmkslhsyesshixytfw.supabase.co/storage/v1/object/public/product-images/123/primary_a1b2c3.jpg",
  "primary_image_source": "bigbasket",
  "category": "snacks",
  "current_version": {
    "version_seq": 1,
    "ingredients": [...],
    "nutrition": {...},
    "squor_score": {
      "score": 72.5,
      "grade": "B"
    }
  }
}
```

## Configuration

### Required Environment Variables

```bash
# Database (existing)
DATABASE_URL=postgresql://...

# AI Analysis (existing)
GOOGLE_API_KEY=AIza...

# Image Hosting (new)
SUPABASE_ANON_KEY=eyJhbGci...
```

### Optional: Custom Storage

If you don't want to use Supabase Storage, you can modify `ImageHostingService` to use:
- AWS S3
- Cloudinary
- Local file storage
- Any S3-compatible storage

## Benefits

1. **Independence**: Not relying on retailer image URLs
2. **Performance**: Images served from CDN
3. **Consistency**: All images optimized to same standards
4. **Cost-effective**: Free for up to 1GB storage
5. **Simple**: No additional infrastructure needed

## Frontend Usage

### React Example

```jsx
function ProductGrid() {
  const [products, setProducts] = useState([]);
  
  useEffect(() => {
    fetch('/api/v1/products')
      .then(res => res.json())
      .then(data => setProducts(data.items));
  }, []);
  
  return (
    <div className="grid grid-cols-4 gap-4">
      {products.map(product => (
        <div key={product.product_id} className="product-card">
          <img 
            src={product.primary_image_url}
            alt={product.name}
            className="w-full h-48 object-cover"
          />
          <h3>{product.name}</h3>
          <p>{product.brand.name}</p>
          <div className="squor-badge">
            {product.current_version?.squor_score?.grade || 'N/A'}
          </div>
        </div>
      ))}
    </div>
  );
}
```

### Next.js with Image Optimization

```jsx
import Image from 'next/image';

function ProductCard({ product }) {
  return (
    <div>
      <Image
        src={product.primary_image_url}
        alt={product.name}
        width={300}
        height={300}
        placeholder="blur"
        blurDataURL="/placeholder.png"
      />
    </div>
  );
}
```

## Monitoring

Check image hosting status:

```sql
-- Products with hosted images
SELECT COUNT(*) FROM product WHERE primary_image_url IS NOT NULL;

-- Products by image source
SELECT primary_image_source, COUNT(*) 
FROM product 
WHERE primary_image_url IS NOT NULL 
GROUP BY primary_image_source;

-- Recent image uploads
SELECT 
  p.name,
  p.primary_image_url,
  p.updated_at
FROM product p
WHERE p.primary_image_url IS NOT NULL
ORDER BY p.updated_at DESC
LIMIT 10;
```

## Troubleshooting

### No image selected
- Check if Gemini response includes `best_image`
- Verify image URLs are accessible
- Check logs for download errors

### Upload failures
- Verify `SUPABASE_ANON_KEY` is set
- Check Supabase storage quota
- Ensure bucket exists and is public

### Poor image quality
- Original image may be low quality
- Try adjusting optimization settings
- Consider higher quality threshold

## Future Enhancements

1. **Multiple angles**: Store front, back, nutrition images
2. **Image recognition**: Verify image matches product
3. **Background removal**: Clean product shots
4. **WebP format**: Better compression
5. **Lazy loading**: Progressive image loading
