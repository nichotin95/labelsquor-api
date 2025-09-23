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
    Synchronous crawl that returns results immediately
    Uses subprocess to run crawler with proxy support
    """
    import subprocess
    import json
    
    if request.retailer != "bigbasket":
        return {"error": "Only BigBasket supported currently", "products_found": 0, "sample": []}
    
    # Run crawler synchronously
    cmd = [
        "python", "run_crawler.py",
        request.retailer,
        "--search-terms", ",".join(request.search_terms),
        "--max-products", str(request.max_products),
        "--output-format", "json"  # Request JSON output
    ]
    
    env = os.environ.copy()
    api_url = os.environ.get("LABELSQUOR_API_URL", "https://labelsquor-api-u7wurf5zba-uc.a.run.app")
    env["LABELSQUOR_API_URL"] = api_url
    
    print(f"🕷️ Running simple crawl for {request.retailer}")
    print(f"   Command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=env,
            cwd="/app",
            timeout=30  # 30 second timeout
        )
        
        if result.returncode == 0:
            # Parse output to find JSON results
            output_lines = result.stdout.strip().split('\n')
            products = []
            
            for line in output_lines:
                if line.startswith('✅ Found:'):
                    # Extract product info from output
                    parts = line.split(' - ')
                    if len(parts) >= 2:
                        name = parts[0].replace('✅ Found:', '').strip()
                        price = parts[1].strip() if len(parts) > 1 else "₹0"
                        products.append({
                            "name": name,
                            "price": price,
                            "retailer": request.retailer,
                            "url": f"https://www.bigbasket.com/pd/{name.lower().replace(' ', '-')}/",
                        })
            
            # Also check if there's a JSON output file
            try:
                with open(f"{request.retailer}_results.json", "r") as f:
                    json_products = json.load(f)
                    if json_products:
                        products = json_products[:request.max_products]
            except:
                pass
            
            print(f"✅ Simple crawl found {len(products)} products")
            
            return {
                "products_found": len(products),
                "products_sent": 0,  # Not sending in simple mode
                "sample": products[:10],  # Return up to 10 products
                "proxy_used": "gcp" in env.get("SCRAPY_SETTINGS_MODULE", "").lower()
            }
        else:
            print(f"❌ Crawler failed: {result.stderr}")
            return {
                "error": "Crawler failed",
                "products_found": 0,
                "sample": [],
                "details": result.stderr[:500]
            }
            
    except subprocess.TimeoutExpired:
        return {
            "error": "Crawler timeout",
            "products_found": 0,
            "sample": []
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
