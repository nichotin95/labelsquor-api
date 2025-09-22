# Image Hosting Setup Guide

## Overview

LabelSquor uses Supabase Storage to host product images. This ensures:
- Images are served from our own domain
- No dependency on retailer image URLs
- Free hosting up to 1GB storage
- Fast CDN delivery

## How It Works

1. **Gemini Analysis**: When analyzing a product, Gemini selects the best image based on:
   - Clear product visibility
   - Good lighting and focus
   - Front-facing view preferred
   - Professional appearance

2. **Image Upload**: The selected image is:
   - Downloaded from the retailer
   - Optimized (resized to max 800x800, compressed)
   - Uploaded to Supabase Storage
   - URL saved to `product.primary_image_url`

3. **Frontend Display**: Use the `primary_image_url` field to display product images

## Setup Instructions

### 1. Get Your Supabase Anon Key

Since you're already using Supabase for your database, you just need to get the anon key:

1. Go to your Supabase project dashboard
2. Click on "Settings" → "API"
3. Copy the `anon` public key (not the service key!)

### 2. Add to Environment Variables

Add to your `.env` file:

```bash
# Existing database URL
DATABASE_URL=postgresql://postgres:password@db.project-ref.supabase.co:5432/postgres

# Add this new line
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...your-anon-key-here
```

### 3. Storage Bucket Setup

The system will automatically create a `product-images` bucket on first use. Or you can create it manually:

1. Go to Supabase Dashboard → Storage
2. Create new bucket named `product-images`
3. Make it public (so frontend can access images)
4. Set file size limit to 5MB
5. Allow mime types: `image/jpeg`, `image/png`, `image/webp`

## Image URLs Format

Images are stored with this structure:
```
https://your-project.supabase.co/storage/v1/object/public/product-images/{product_id}/primary_{hash}.jpg
```

Example:
```
https://snjmkslhsyesshixytfw.supabase.co/storage/v1/object/public/product-images/123e4567-e89b-12d3-a456-426614174000/primary_a1b2c3d4.jpg
```

## API Response

Products now include the hosted image URL:

```json
{
  "product_id": "123e4567-e89b-12d3-a456-426614174000",
  "name": "Maggi 2-Minute Noodles",
  "brand": {
    "name": "Maggi"
  },
  "primary_image_url": "https://your-project.supabase.co/storage/v1/object/public/product-images/123e4567/primary_a1b2c3.jpg",
  "primary_image_source": "bigbasket"
}
```

## Fallback Behavior

If Supabase anon key is not configured:
- System will log a warning
- Original retailer URL will be used (not recommended)
- No image optimization will occur

## Cost Considerations

Supabase Free Tier includes:
- 1GB storage (enough for ~10,000 product images)
- 2GB bandwidth per month
- Unlimited API requests

For scale beyond this, consider:
- Supabase Pro plan ($25/month)
- Alternative: Cloudinary (generous free tier)
- Alternative: AWS S3 + CloudFront

## Testing

Test the integration:

```python
# Run crawler with image hosting
python examples/api_crawler_example.py crawl

# Check if image was uploaded
# Look for log: "Updated product {id} with primary image: {url}"
```

## Frontend Integration

```javascript
// React example
function ProductCard({ product }) {
  return (
    <div className="product-card">
      <img 
        src={product.primary_image_url || '/placeholder.png'}
        alt={product.name}
        loading="lazy"
      />
      <h3>{product.name}</h3>
      <p>{product.brand.name}</p>
    </div>
  );
}
```

## Troubleshooting

### Images not uploading
1. Check if `SUPABASE_ANON_KEY` is set
2. Verify the key is the `anon` key, not service key
3. Check Supabase storage quota

### Image quality issues
- System automatically optimizes images
- Max size is 800x800 pixels
- JPEG quality is set to 85%

### CORS errors
- Supabase storage is public by default
- If issues, check bucket settings in Supabase dashboard

## Migration for Existing Products

To upload images for existing products:

```python
# Script to migrate existing products
async def migrate_product_images():
    products = await get_products_without_primary_image()
    
    for product in products:
        if product.source_pages and product.source_pages[0].extracted_data:
            images = product.source_pages[0].extracted_data.get('images', [])
            if images:
                # Re-analyze to select best image
                # Upload to storage
                # Update product
                pass
```
