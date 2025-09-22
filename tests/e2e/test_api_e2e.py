#!/usr/bin/env python3
"""
End-to-end test for the Category Crawl API
"""

import asyncio
import json
import time
import requests
from datetime import datetime


def test_category_crawl_api():
    """Test the complete flow of category crawl API"""
    
    base_url = "http://localhost:8000"
    
    print("\n🚀 Starting Category Crawl API Test")
    print("=" * 50)
    
    # 1. Start a crawl
    print("\n1️⃣  Starting crawl for 'snacks' category...")
    
    crawl_request = {
        "category": "snacks",
        "retailers": ["bigbasket"],
        "max_products": 3,
        "analyze_products": True,
        "consolidate_variants": True,
        "skip_existing": False
    }
    
    response = requests.post(
        f"{base_url}/api/v1/crawler/crawl/category",
        json=crawl_request
    )
    
    if response.status_code != 200:
        print(f"❌ Failed to start crawl: {response.status_code}")
        print(f"Response: {response.text}")
        return
    
    crawl_data = response.json()
    session_id = crawl_data['session_id']
    
    print(f"✅ Crawl started successfully!")
    print(f"   Session ID: {session_id}")
    print(f"   Status: {crawl_data['status']}")
    
    # 2. Poll for status
    print("\n2️⃣  Checking crawl status...")
    
    max_attempts = 30  # Wait up to 5 minutes
    attempt = 0
    
    while attempt < max_attempts:
        time.sleep(10)  # Wait 10 seconds between checks
        attempt += 1
        
        response = requests.get(
            f"{base_url}/api/v1/crawler/status/{session_id}"
        )
        
        if response.status_code != 200:
            print(f"❌ Failed to get status: {response.status_code}")
            print(f"Response: {response.text}")
            return
        
        status_data = response.json()
        status = status_data['status']
        
        print(f"\n   Attempt {attempt}/{max_attempts}")
        print(f"   Status: {status}")
        print(f"   Products found: {status_data['products_found']}")
        print(f"   Products analyzed: {status_data['products_analyzed']}")
        
        if status in ['completed', 'failed']:
            break
    
    # 3. Final results
    print("\n3️⃣  Final Results")
    print("=" * 50)
    
    if status == 'completed':
        print("✅ Crawl completed successfully!")
        print(f"   Products found: {status_data['products_found']}")
        print(f"   Products analyzed: {status_data['products_analyzed']}")
        print(f"   Products skipped: {status_data['products_skipped']}")
        
        if status_data.get('errors'):
            print(f"\n⚠️  Errors encountered:")
            for error in status_data['errors']:
                print(f"   - {error}")
    else:
        print(f"❌ Crawl failed with status: {status}")
        if status_data.get('errors'):
            print(f"\nErrors:")
            for error in status_data['errors']:
                print(f"   - {error}")
    
    print("\n✨ Test completed!")
    

if __name__ == "__main__":
    test_category_crawl_api()
