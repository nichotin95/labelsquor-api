#!/usr/bin/env python3
"""
Crawler service that runs on GCP with proxy rotation
Receives HTTP requests and triggers crawls with anti-blocking measures
"""
import os
import json
import asyncio
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional
import subprocess
import sys

# Add crawler path
sys.path.append(os.path.dirname(__file__))

app = FastAPI(title="LabelSquor Crawler Service")

class CrawlRequest(BaseModel):
    retailer: str = "bigbasket"
    search_terms: List[str] = ["maggi"]
    max_products: int = 10
    category: Optional[str] = None


class CrawlResponse(BaseModel):
    status: str
    message: str
    task_id: str


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": "LabelSquor Crawler",
        "status": "running",
        "environment": os.environ.get("SCRAPY_SETTINGS_MODULE", "default"),
        "proxy_enabled": "gcp" in os.environ.get("SCRAPY_SETTINGS_MODULE", "").lower()
    }


@app.get("/test-proxy")
async def test_proxy():
    """Test proxy functionality"""
    import httpx
    
    # Try to get current IP
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("https://api.ipify.org?format=json", timeout=10)
            direct_ip = response.json()["ip"]
    except:
        direct_ip = "Failed to get IP"
    
    # Test if we're in GCP environment
    is_gcp = "gcp" in os.environ.get("SCRAPY_SETTINGS_MODULE", "").lower()
    
    # Test BigBasket access
    test_url = "https://www.bigbasket.com/api/v3.0/header/get-header-config/"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(test_url, timeout=10)
            bigbasket_status = response.status_code
            bigbasket_response = "Success" if bigbasket_status == 200 else f"Status: {bigbasket_status}"
    except Exception as e:
        bigbasket_status = 0
        bigbasket_response = str(e)
    
    return {
        "direct_ip": direct_ip,
        "is_gcp_environment": is_gcp,
        "bigbasket_test": {
            "status_code": bigbasket_status,
            "response": bigbasket_response
        },
        "proxy_info": "Proxy rotation enabled via Scrapy middleware" if is_gcp else "No proxy"
    }


@app.get("/proxy-demo")
async def proxy_demo():
    """Demonstrate proxy working with actual request"""
    import httpx
    import requests
    
    # Get a proxy from free sources
    proxy_urls = [
        'https://api.proxyscrape.com/v2/?request=get&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all&limit=5',
    ]
    
    proxies = []
    for url in proxy_urls:
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                for line in resp.text.strip().split('\n')[:5]:
                    if ':' in line:
                        proxies.append(f"http://{line.strip()}")
        except:
            pass
    
    results = {
        "direct_test": {},
        "proxy_tests": [],
        "working_proxies": []
    }
    
    # Test direct
    test_url = "https://httpbin.org/ip"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(test_url, timeout=5)
            results["direct_test"] = {
                "status": resp.status_code,
                "ip": resp.json().get("origin", "Unknown")
            }
    except Exception as e:
        results["direct_test"] = {"error": str(e)}
    
    # Test with proxies
    for proxy in proxies[:3]:  # Test first 3
        try:
            async with httpx.AsyncClient(proxies={"http://": proxy, "https://": proxy}) as client:
                resp = await client.get(test_url, timeout=5)
                proxy_result = {
                    "proxy": proxy,
                    "status": resp.status_code,
                    "ip": resp.json().get("origin", "Unknown")
                }
                results["proxy_tests"].append(proxy_result)
                if resp.status_code == 200:
                    results["working_proxies"].append(proxy)
        except Exception as e:
            results["proxy_tests"].append({
                "proxy": proxy,
                "error": str(e)[:50]
            })
    
    # Test BigBasket with working proxy
    if results["working_proxies"]:
        bb_url = "https://www.bigbasket.com/api/v3.0/header/get-header-config/"
        proxy = results["working_proxies"][0]
        try:
            async with httpx.AsyncClient(proxies={"http://": proxy, "https://": proxy}) as client:
                resp = await client.get(bb_url, timeout=10)
                results["bigbasket_with_proxy"] = {
                    "proxy_used": proxy,
                    "status": resp.status_code,
                    "success": resp.status_code == 200
                }
        except Exception as e:
            results["bigbasket_with_proxy"] = {"error": str(e)[:100]}
    
    return results


@app.post("/crawl", response_model=CrawlResponse)
async def trigger_crawl(request: CrawlRequest, background_tasks: BackgroundTasks):
    """Trigger a crawl with anti-blocking measures"""
    
    # Generate task ID
    import uuid
    task_id = str(uuid.uuid4())
    
    # Add background task
    background_tasks.add_task(
        run_crawler,
        task_id=task_id,
        retailer=request.retailer,
        search_terms=request.search_terms,
        max_products=request.max_products
    )
    
    return CrawlResponse(
        status="started",
        message=f"Crawl started for {request.retailer}",
        task_id=task_id
    )


def run_crawler(task_id: str, retailer: str, search_terms: List[str], max_products: int):
    """Run the crawler with proxy rotation"""
    
    print(f"🕷️ Starting crawler task {task_id} for {retailer}")
    print(f"   Search terms: {search_terms}")
    print(f"   Max products: {max_products}")
    
    # Set API URL from environment or default
    api_url = os.environ.get("LABELSQUOR_API_URL", "https://labelsquor-api-u7wurf5zba-uc.a.run.app")
    
    # Always use subprocess to avoid reactor conflicts in async environment
    cmd = [
        "python", "run_crawler.py",
        retailer,
        "--search-terms", ",".join(search_terms),
        "--max-products", str(max_products)
    ]
    
    env = os.environ.copy()
    env["LABELSQUOR_API_URL"] = api_url
    
    try:
        print(f"📡 Running command: {' '.join(cmd)}")
        print(f"🔧 Environment: SCRAPY_SETTINGS_MODULE={env.get('SCRAPY_SETTINGS_MODULE', 'not set')}")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=env,
            cwd="/app"  # Ensure correct working directory
        )
        
        if result.returncode == 0:
            print(f"✅ Task {task_id} completed successfully")
            print(f"Output:\n{result.stdout}")
            
            # Check if any products were found
            if "Found:" in result.stdout:
                found_count = result.stdout.count("Found:")
                print(f"📦 Products found: {found_count}")
            else:
                print("⚠️ No products found - proxy may not be working")
        else:
            print(f"❌ Task {task_id} failed with code {result.returncode}")
            print(f"Error:\n{result.stderr}")
            
    except Exception as e:
        print(f"❌ Task {task_id} error: {type(e).__name__}: {str(e)}")


@app.post("/crawl/simple", response_model=dict)
async def simple_crawl(request: CrawlRequest):
    """
    Direct proxy crawl that returns results immediately
    Uses httpx with proxy rotation to bypass blocking
    """
    if request.retailer != "bigbasket":
        return {"error": "Only BigBasket supported currently", "products_found": 0, "sample": []}
    
    # Import the simple proxy crawler
    try:
        from simple_proxy_crawler import crawl_bigbasket
        
        print(f"🕷️ Running proxy crawl for {request.retailer}")
        print(f"   Search terms: {request.search_terms}")
        print(f"   Max products: {request.max_products}")
        
        # Run the crawler
        result = await crawl_bigbasket(
            search_terms=request.search_terms,
            max_products=request.max_products
        )
        
        if result.get('success'):
            print(f"✅ Proxy crawl found {result['products_found']} products")
            return {
                "products_found": result['products_found'],
                "products_sent": 0,  # Not sending to API in simple mode
                "sample": result['products'],
                "proxy_used": True,
                "success": True
            }
        else:
            return {
                "error": "No products found - all proxies may be blocked",
                "products_found": 0,
                "sample": [],
                "proxy_used": True,
                "success": False
            }
            
    except ImportError as e:
        print(f"⚠️ Falling back to subprocess method: {e}")
        # Fallback to subprocess method
        import subprocess
        import json
        
        cmd = [
            "python", "simple_proxy_crawler.py",
            ",".join(request.search_terms),
            str(request.max_products)
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd="/app",
                timeout=45
            )
            
            if result.returncode == 0:
                # Parse the output to find JSON
                try:
                    # Find JSON in output
                    output = result.stdout
                    json_start = output.find('{')
                    if json_start != -1:
                        json_str = output[json_start:]
                        data = json.loads(json_str)
                        return {
                            "products_found": data.get('products_found', 0),
                            "products_sent": 0,
                            "sample": data.get('products', []),
                            "proxy_used": True,
                            "success": data.get('success', False)
                        }
                except:
                    pass
            
            return {
                "error": "Crawler failed",
                "products_found": 0,
                "sample": [],
                "details": result.stderr[:300] if result.stderr else result.stdout[:300]
            }
            
        except Exception as e:
            return {
                "error": str(e),
                "products_found": 0,
                "sample": []
            }


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
