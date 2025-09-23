#!/usr/bin/env python3
"""
Test script to verify proxy crawler functionality
"""
import requests
import json
import time

print("🧪 Testing Proxy Crawler Service")
print("=" * 50)

# Test endpoints
base_url = "https://labelsquor-crawler-143169591686.us-central1.run.app"

# 1. Check service health
print("\n1️⃣ Testing service health...")
response = requests.get(f"{base_url}/")
print(f"   Status: {response.status_code}")
print(f"   Response: {response.json()}")

# 2. Test proxy status
print("\n2️⃣ Testing proxy status...")
response = requests.get(f"{base_url}/test-proxy")
data = response.json()
print(f"   GCP IP: {data.get('direct_ip')}")
print(f"   BigBasket blocked: {data.get('bigbasket_test', {}).get('status_code') == 403}")
print(f"   Proxy enabled: {data.get('proxy_enabled')}")

# 3. Test simple crawl
print("\n3️⃣ Testing simple crawl endpoint...")
crawl_data = {
    "retailer": "bigbasket",
    "search_terms": ["maggi", "lays"],
    "max_products": 5
}

print(f"   Request: {json.dumps(crawl_data, indent=2)}")
start_time = time.time()
response = requests.post(
    f"{base_url}/crawl/simple",
    json=crawl_data,
    timeout=60
)
elapsed = time.time() - start_time

print(f"   Status: {response.status_code}")
print(f"   Time taken: {elapsed:.2f}s")

if response.status_code == 200:
    result = response.json()
    print(f"   Products found: {result.get('products_found', 0)}")
    print(f"   Error: {result.get('error', 'None')}")
    
    if result.get('sample'):
        print("\n   Sample products:")
        for i, product in enumerate(result['sample'][:3], 1):
            print(f"   {i}. {product.get('name', 'Unknown')} - {product.get('price', 'N/A')}")
    else:
        print("   ❌ No products returned")
        if result.get('details'):
            print(f"   Details: {result['details'][:200]}...")
else:
    print(f"   ❌ Request failed: {response.text}")

print("\n" + "=" * 50)
print("🏁 Test complete!")
