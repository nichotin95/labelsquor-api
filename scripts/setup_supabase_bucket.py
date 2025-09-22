#!/usr/bin/env python3
"""
Setup Supabase storage bucket for images
"""

import asyncio
import httpx
from app.core.config import settings
from urllib.parse import urlparse

async def setup_bucket():
    if not settings.supabase_anon_key:
        print('❌ SUPABASE_ANON_KEY not set in environment')
        print('   Add it to your .env file from Supabase Dashboard > Settings > API')
        return
    
    # Extract Supabase URL from database URL
    parsed = urlparse(str(settings.database_url))
    host_parts = parsed.hostname.split('.')
    
    if len(host_parts) >= 3 and host_parts[0] == 'db':
        project_ref = host_parts[1]
        supabase_url = f"https://{project_ref}.supabase.co"
        print(f'🔗 Supabase URL: {supabase_url}')
    else:
        print('❌ Could not extract Supabase URL from database URL')
        return
    
    bucket_name = "product-images"
    
    async with httpx.AsyncClient() as client:
        # Set headers
        headers = {
            "apikey": settings.supabase_anon_key,
            "Authorization": f"Bearer {settings.supabase_anon_key}",
            "Content-Type": "application/json"
        }
        
        try:
            # Check if bucket exists
            print(f'🔍 Checking if bucket "{bucket_name}" exists...')
            response = await client.get(
                f"{supabase_url}/storage/v1/bucket/{bucket_name}",
                headers=headers
            )
            
            if response.status_code == 200:
                print(f'✅ Bucket "{bucket_name}" already exists!')
                bucket_info = response.json()
                print(f'   Public: {bucket_info.get("public", False)}')
                return
            
            elif response.status_code == 404:
                # Create bucket
                print(f'📦 Creating bucket "{bucket_name}"...')
                create_response = await client.post(
                    f"{supabase_url}/storage/v1/bucket",
                    headers=headers,
                    json={
                        "id": bucket_name,
                        "name": bucket_name,
                        "public": True,  # Public so frontend can access
                        "file_size_limit": 5242880,  # 5MB limit
                        "allowed_mime_types": ["image/jpeg", "image/png", "image/webp"]
                    }
                )
                
                if create_response.status_code in [200, 201]:
                    print(f'✅ Created bucket "{bucket_name}" successfully!')
                    print(f'   Public URL format: {supabase_url}/storage/v1/object/public/{bucket_name}/{{filename}}')
                else:
                    print(f'❌ Failed to create bucket: {create_response.status_code}')
                    print(f'   Response: {create_response.text}')
            
            else:
                print(f'❌ Unexpected response: {response.status_code}')
                print(f'   Response: {response.text}')
                
        except Exception as e:
            print(f'❌ Error setting up bucket: {e}')

if __name__ == "__main__":
    asyncio.run(setup_bucket())
