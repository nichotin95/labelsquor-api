#!/usr/bin/env python3
"""
Test script for LabelSquor API endpoints
"""
import requests
import json
import time
from typing import Dict, Any

# API Base URL
BASE_URL = "http://localhost:8000/api/v1"

def test_health():
    """Test health endpoint"""
    print("🔍 Testing health endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/health")
        print(f"✅ Health check: {response.status_code}")
        print(f"   Response: {response.json()}")
        return True
    except Exception as e:
        print(f"❌ Health check failed: {str(e)}")
        return False

def test_crawl_category(category: str = "snacks", max_products: int = 3):
    """Test category crawling API"""
    print(f"\n🕷️ Testing category crawl: {category} (max {max_products} products)...")
    
    payload = {
        "category": category,
        "retailers": ["bigbasket"],  # Start with just BigBasket
        "max_products": max_products,
        "skip_existing": True,
        "consolidate_variants": True
    }
    
    try:
        response = requests.post(f"{BASE_URL}/crawler/crawl/category", json=payload)
        print(f"✅ Crawl request: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            session_id = data.get("session_id")
            print(f"   Session ID: {session_id}")
            print(f"   Status: {data.get('status')}")
            print(f"   Message: {data.get('message')}")
            return session_id
        else:
            print(f"   Error: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Crawl request failed: {str(e)}")
        return None

def test_crawl_status(session_id: str):
    """Test crawl status checking"""
    print(f"\n📊 Checking crawl status for session: {session_id}")
    
    try:
        response = requests.get(f"{BASE_URL}/crawler/status/{session_id}")
        print(f"✅ Status check: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   Status: {data.get('status')}")
            print(f"   Products found: {data.get('products_found', 0)}")
            print(f"   Products analyzed: {data.get('products_analyzed', 0)}")
            print(f"   Message: {data.get('message')}")
            return data.get('status')
        else:
            print(f"   Error: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Status check failed: {str(e)}")
        return None

def test_recent_products():
    """Test getting recent products"""
    print(f"\n📦 Getting recent products...")
    
    try:
        response = requests.get(f"{BASE_URL}/crawler/products/recent?limit=5")
        print(f"✅ Recent products: {response.status_code}")
        
        if response.status_code == 200:
            products = response.json()
            print(f"   Found {len(products)} recent products:")
            for product in products:
                print(f"   - {product.get('name')} ({product.get('brand')})")
                print(f"     SQUOR: {product.get('squor_score', 0):.1f} {product.get('squor_rating', '')}")
            return products
        else:
            print(f"   Error: {response.text}")
            return []
            
    except Exception as e:
        print(f"❌ Recent products failed: {str(e)}")
        return []

def test_search_product(product_name: str = "maggi"):
    """Test product search"""
    print(f"\n🔍 Searching for product: {product_name}")
    
    payload = {
        "product_name": product_name,
        "retailers": ["bigbasket"],
        "analyze_immediately": True
    }
    
    try:
        response = requests.post(f"{BASE_URL}/crawler/search/product", json=payload)
        print(f"✅ Product search: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   Product: {data.get('name')}")
            print(f"   Brand: {data.get('brand')}")
            print(f"   Status: {data.get('analysis_status')}")
            print(f"   Sources: {data.get('sources', [])}")
            return data
        else:
            print(f"   Error: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Product search failed: {str(e)}")
        return None

def test_complete_flow():
    """Test the complete flow from crawling to analysis"""
    print("\n" + "="*60)
    print("🚀 TESTING COMPLETE LABELSQUOR API FLOW")
    print("="*60)
    
    # 1. Health check
    if not test_health():
        print("❌ Health check failed - stopping tests")
        return
    
    time.sleep(1)
    
    # 2. Start category crawl
    session_id = test_crawl_category("snacks", 3)
    if not session_id:
        print("❌ Category crawl failed - stopping tests")
        return
    
    # 3. Monitor crawl progress
    print("\n⏳ Monitoring crawl progress...")
    max_attempts = 30  # 5 minutes max
    attempt = 0
    
    while attempt < max_attempts:
        time.sleep(10)  # Wait 10 seconds between checks
        attempt += 1
        
        status = test_crawl_status(session_id)
        if status in ["completed", "failed"]:
            break
        elif status == "running":
            print(f"   Still running... (attempt {attempt}/{max_attempts})")
        else:
            print(f"   Unknown status: {status}")
    
    # 4. Check recent products
    time.sleep(2)
    recent_products = test_recent_products()
    
    # 5. Test individual product search
    time.sleep(2)
    test_search_product("maggi noodles")
    
    print("\n" + "="*60)
    print("✅ COMPLETE API TEST FINISHED")
    print("="*60)
    
    # Summary
    if recent_products:
        print(f"\n📊 SUMMARY:")
        print(f"   - Crawl session: {session_id}")
        print(f"   - Final status: {status}")
        print(f"   - Products found: {len(recent_products)}")
        print(f"   - API endpoints tested: 5/5 ✅")
    else:
        print(f"\n⚠️  Some tests may have failed - check the logs above")

def test_api_docs():
    """Test API documentation endpoints"""
    print("\n📚 Testing API documentation...")
    
    try:
        # Test docs endpoint
        response = requests.get("http://localhost:8000/docs")
        print(f"✅ API Docs: {response.status_code}")
        
        # Test OpenAPI schema
        response = requests.get("http://localhost:8000/openapi.json")
        print(f"✅ OpenAPI Schema: {response.status_code}")
        
        if response.status_code == 200:
            schema = response.json()
            endpoints = []
            for path, methods in schema.get("paths", {}).items():
                for method in methods.keys():
                    endpoints.append(f"{method.upper()} {path}")
            
            print(f"   Available endpoints: {len(endpoints)}")
            for endpoint in sorted(endpoints)[:10]:  # Show first 10
                print(f"   - {endpoint}")
            if len(endpoints) > 10:
                print(f"   ... and {len(endpoints) - 10} more")
        
    except Exception as e:
        print(f"❌ API docs test failed: {str(e)}")

if __name__ == "__main__":
    print("""
    🧪 LABELSQUOR API TEST SUITE
    =============================
    
    This script will test the complete API workflow:
    1. Health checks
    2. Category crawling
    3. Product analysis
    4. Data retrieval
    
    Make sure the API server is running on localhost:8000
    """)
    
    # Quick connectivity test
    try:
        response = requests.get("http://localhost:8000/", timeout=5)
        print(f"✅ API server is running (status: {response.status_code})")
    except Exception as e:
        print(f"❌ Cannot connect to API server: {str(e)}")
        print("\nTo start the server, run:")
        print("   python simple_main.py")
        exit(1)
    
    # Test API documentation first
    test_api_docs()
    
    # Ask user what to test
    choice = input("\nWhat would you like to test?\n1. Complete flow (recommended)\n2. Individual endpoints\n3. Just health check\nChoice (1-3): ").strip()
    
    if choice == "1" or choice == "":
        test_complete_flow()
    elif choice == "2":
        print("\nTesting individual endpoints...")
        test_health()
        session_id = test_crawl_category("snacks", 2)
        if session_id:
            time.sleep(5)
            test_crawl_status(session_id)
        test_recent_products()
        test_search_product("maggi")
    elif choice == "3":
        test_health()
    else:
        print("Invalid choice")
