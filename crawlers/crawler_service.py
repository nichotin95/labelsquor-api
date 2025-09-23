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
    
    # Set API URL from environment or default
    api_url = os.environ.get("LABELSQUOR_API_URL", "https://labelsquor-api-u7wurf5zba-uc.a.run.app")
    
    # Use the run_crawler.py script
    cmd = [
        "python", "run_crawler.py",
        retailer,
        "--search-terms", ",".join(search_terms),
        "--max-products", str(max_products)
    ]
    
    # Set environment
    env = os.environ.copy()
    env["LABELSQUOR_API_URL"] = api_url
    
    try:
        # Run crawler
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=env
        )
        
        if result.returncode == 0:
            print(f"Task {task_id} completed successfully")
            print(f"Output: {result.stdout}")
        else:
            print(f"Task {task_id} failed: {result.stderr}")
            
    except Exception as e:
        print(f"Task {task_id} error: {str(e)}")


@app.post("/crawl/simple", response_model=dict)
async def simple_crawl(request: CrawlRequest):
    """Direct crawl using simple parser (immediate response)"""
    
    from simple_bigbasket_parser import SimpleBigBasketParser
    import httpx
    
    if request.retailer != "bigbasket":
        return {"error": "Only BigBasket supported for simple crawl"}
    
    parser = SimpleBigBasketParser()
    all_products = []
    
    for term in request.search_terms:
        products = parser.search_products(term)
        all_products.extend(products[:request.max_products // len(request.search_terms)])
    
    # Send to API
    api_url = os.environ.get("LABELSQUOR_API_URL", "https://labelsquor-api-u7wurf5zba-uc.a.run.app")
    sent_count = 0
    
    async with httpx.AsyncClient() as client:
        for product in all_products[:request.max_products]:
            try:
                response = await client.post(
                    f"{api_url}/api/v1/crawler/products",
                    json={
                        "source_page": {
                            "url": product["url"],
                            "retailer": "bigbasket",
                            "title": product["name"],
                            "content_hash": f"crawler_{hash(product['url'])}",
                            "extracted_data": product
                        }
                    }
                )
                if response.status_code in [200, 201]:
                    sent_count += 1
            except Exception as e:
                print(f"Failed to send product: {e}")
    
    return {
        "products_found": len(all_products),
        "products_sent": sent_count,
        "sample": all_products[:3] if all_products else []
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
