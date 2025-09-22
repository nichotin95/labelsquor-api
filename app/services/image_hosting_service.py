"""
Image hosting service using Supabase Storage
"""

import io
import hashlib
from typing import Optional, Tuple
from uuid import uuid4
import httpx
from PIL import Image
from urllib.parse import urlparse

from app.core.config import settings
from app.core.logging import log


class ImageHostingService:
    """
    Service for hosting product images on Supabase Storage
    Free tier: 1GB storage, 2GB bandwidth per month
    """
    
    def __init__(self):
        # Extract Supabase URL and anon key from database URL
        # Format: postgresql://postgres:[password]@db.[project-ref].supabase.co:5432/postgres
        parsed = urlparse(str(settings.database_url))
        host_parts = parsed.hostname.split('.')
        
        if len(host_parts) >= 3 and host_parts[0] == 'db':
            self.project_ref = host_parts[1]
            self.supabase_url = f"https://{self.project_ref}.supabase.co"
        else:
            # Fallback for local development
            self.project_ref = "local"
            self.supabase_url = "https://your-project.supabase.co"
        
        # You'll need to add SUPABASE_ANON_KEY to your .env file
        self.anon_key = settings.supabase_anon_key if hasattr(settings, 'supabase_anon_key') else None
        self.bucket_name = "product-images"
        
        # Initialize HTTP client
        self.client = httpx.AsyncClient(
            headers={
                "apikey": self.anon_key or "",
                "Authorization": f"Bearer {self.anon_key or ''}"
            } if self.anon_key else {}
        )
    
    async def setup_bucket(self) -> bool:
        """Create the storage bucket if it doesn't exist"""
        try:
            # Check if bucket exists
            response = await self.client.get(
                f"{self.supabase_url}/storage/v1/bucket/{self.bucket_name}"
            )
            
            if response.status_code == 404:
                # Create bucket
                response = await self.client.post(
                    f"{self.supabase_url}/storage/v1/bucket",
                    json={
                        "id": self.bucket_name,
                        "name": self.bucket_name,
                        "public": True,  # Public so frontend can access
                        "file_size_limit": 5242880,  # 5MB limit
                        "allowed_mime_types": ["image/jpeg", "image/png", "image/webp"]
                    }
                )
                
                if response.status_code == 200:
                    log.info(f"Created storage bucket: {self.bucket_name}")
                    return True
                else:
                    log.error(f"Failed to create bucket: {response.text}")
                    return False
            
            return True
            
        except Exception as e:
            log.error(f"Error setting up bucket: {e}")
            return False
    
    async def upload_image_from_url(
        self, 
        image_url: str, 
        product_id: str,
        image_type: str = "primary"
    ) -> Optional[str]:
        """
        Download image from URL and upload to Supabase Storage
        Returns the hosted URL or None if failed
        """
        if not self.anon_key:
            log.warning("Supabase anon key not configured, using original URL")
            return image_url
        
        # Ensure bucket exists
        if not await self.setup_bucket():
            log.warning("Supabase bucket not available, skipping image upload")
            return None  # Return None instead of original URL to indicate no hosted image
        
        try:
            # Download image
            async with httpx.AsyncClient() as download_client:
                response = await download_client.get(
                    image_url,
                    follow_redirects=True,
                    timeout=30.0,
                    headers={
                        "User-Agent": "Mozilla/5.0 (compatible; LabelSquor/1.0)"
                    }
                )
                
                if response.status_code != 200:
                    log.error(f"Failed to download image: {response.status_code}")
                    return None
                
                image_data = response.content
            
            # Generate hash for deduplication
            image_hash = hashlib.sha256(image_data).hexdigest()[:12]
            
            # Optimize image (resize if too large, convert to JPEG)
            optimized_data, mime_type = await self._optimize_image(image_data)
            
            # Generate filename
            extension = "jpg" if mime_type == "image/jpeg" else "png"
            filename = f"{product_id}/{image_type}_{image_hash}.{extension}"
            
            # Upload to Supabase
            upload_response = await self.client.post(
                f"{self.supabase_url}/storage/v1/object/{self.bucket_name}/{filename}",
                content=optimized_data,
                headers={
                    "Content-Type": mime_type,
                    "Cache-Control": "public, max-age=31536000"  # 1 year cache
                }
            )
            
            if upload_response.status_code in [200, 201]:
                # Return public URL
                public_url = f"{self.supabase_url}/storage/v1/object/public/{self.bucket_name}/{filename}"
                log.info(f"Successfully uploaded image: {public_url}")
                return public_url
            else:
                log.error(f"Failed to upload image: {upload_response.text}")
                return None
                
        except Exception as e:
            log.error(f"Error uploading image: {e}")
            return None
    
    async def _optimize_image(self, image_data: bytes) -> Tuple[bytes, str]:
        """
        Optimize image for web display
        - Resize if larger than 800x800
        - Convert to JPEG for photos, keep PNG for graphics
        - Compress to reduce size
        """
        try:
            # Open image
            img = Image.open(io.BytesIO(image_data))
            
            # Convert RGBA to RGB if needed
            if img.mode in ('RGBA', 'LA'):
                # Create white background
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'RGBA':
                    background.paste(img, mask=img.split()[3])
                else:
                    background.paste(img, mask=img.split()[1])
                img = background
            elif img.mode not in ('RGB', 'L'):
                img = img.convert('RGB')
            
            # Resize if too large
            max_size = (800, 800)
            if img.size[0] > max_size[0] or img.size[1] > max_size[1]:
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # Save optimized image
            output = io.BytesIO()
            
            # Determine format based on image characteristics
            # Use PNG for images with few colors (logos, graphics)
            # Use JPEG for photos
            if self._is_photo_like(img):
                img.save(output, format='JPEG', quality=85, optimize=True)
                mime_type = 'image/jpeg'
            else:
                img.save(output, format='PNG', optimize=True)
                mime_type = 'image/png'
            
            return output.getvalue(), mime_type
            
        except Exception as e:
            log.error(f"Error optimizing image: {e}")
            # Return original if optimization fails
            return image_data, 'image/jpeg'
    
    def _is_photo_like(self, img: Image.Image) -> bool:
        """
        Determine if image is photo-like (many colors) or graphic-like (few colors)
        """
        # Sample the image to count unique colors
        small = img.copy()
        small.thumbnail((100, 100))
        colors = set(small.getdata())
        
        # If more than 1000 unique colors, it's likely a photo
        return len(colors) > 1000
    
    async def select_best_image(self, image_urls: list[str], gemini_scores: dict) -> Optional[str]:
        """
        Select the best image based on Gemini's analysis scores
        
        gemini_scores format:
        {
            "url1": {"quality": 0.9, "relevance": 0.8, "clarity": 0.85},
            "url2": {"quality": 0.7, "relevance": 0.9, "clarity": 0.8},
        }
        """
        if not image_urls:
            return None
        
        # If no scores, return first image
        if not gemini_scores:
            return image_urls[0]
        
        # Calculate composite score for each image
        best_url = None
        best_score = -1
        
        for url in image_urls:
            if url in gemini_scores:
                scores = gemini_scores[url]
                # Weighted average: quality (40%), relevance (40%), clarity (20%)
                composite = (
                    scores.get('quality', 0) * 0.4 +
                    scores.get('relevance', 0) * 0.4 +
                    scores.get('clarity', 0) * 0.2
                )
                
                if composite > best_score:
                    best_score = composite
                    best_url = url
        
        return best_url or image_urls[0]
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()


# Global instance
image_hosting_service = ImageHostingService()
