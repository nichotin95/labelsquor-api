"""
Anti-blocking middlewares for LabelSquor crawlers
Handles proxy rotation, user-agent rotation, and other anti-bot measures
"""
import random
import requests
from scrapy import signals
from scrapy.downloadermiddlewares.retry import RetryMiddleware
from scrapy.exceptions import NotConfigured
from typing import List, Dict, Optional
import json
from urllib.parse import urlparse


class RotatingProxyMiddleware:
    """
    Middleware for rotating proxies from free proxy sources
    """
    
    def __init__(self):
        self.proxies = []
        self.current_proxy = None
        self.proxy_index = 0
        self.fetch_free_proxies()
    
    def fetch_free_proxies(self):
        """Fetch free proxies from multiple sources"""
        proxy_sources = [
            # Free proxy APIs
            'https://api.proxyscrape.com/v2/?request=get&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all&simplified=true',
            'https://www.proxy-list.download/api/v1/get?type=http',
            'https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt',
        ]
        
        all_proxies = []
        
        for source in proxy_sources:
            try:
                response = requests.get(source, timeout=10)
                if response.status_code == 200:
                    # Parse proxies based on response format
                    if 'json' in response.headers.get('content-type', ''):
                        data = response.json()
                        if isinstance(data, list):
                            all_proxies.extend([f"http://{p['ip']}:{p['port']}" for p in data if 'ip' in p])
                    else:
                        # Text format (one proxy per line)
                        proxies = response.text.strip().split('\n')
                        all_proxies.extend([f"http://{p.strip()}" for p in proxies if p.strip()])
            except Exception as e:
                print(f"Failed to fetch proxies from {source}: {e}")
        
        # Filter and validate proxies
        self.proxies = list(set(all_proxies))[:50]  # Limit to 50 unique proxies
        print(f"Loaded {len(self.proxies)} free proxies")
    
    def process_request(self, request, spider):
        """Add proxy to request"""
        if not self.proxies:
            return None
        
        # Skip proxy for local testing
        if 'localhost' in request.url or '127.0.0.1' in request.url:
            return None
        
        # Rotate proxy
        self.current_proxy = self.proxies[self.proxy_index % len(self.proxies)]
        self.proxy_index += 1
        
        request.meta['proxy'] = self.current_proxy
        spider.logger.debug(f'Using proxy: {self.current_proxy}')
    
    def process_exception(self, request, exception, spider):
        """Handle proxy failures"""
        if 'proxy' in request.meta:
            proxy = request.meta['proxy']
            spider.logger.warning(f'Proxy {proxy} failed, removing from list')
            try:
                self.proxies.remove(proxy)
            except ValueError:
                pass
            
            # Retry with different proxy
            return request.replace(dont_filter=True)


class RotatingUserAgentMiddleware:
    """
    Rotate user agents to appear more like real browsers
    """
    
    def __init__(self):
        self.user_agents = [
            # Chrome
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            
            # Firefox
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:120.0) Gecko/20100101 Firefox/120.0',
            
            # Safari
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
            
            # Edge
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
            
            # Mobile browsers
            'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
            'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
        ]
    
    def process_request(self, request, spider):
        """Set random user agent"""
        ua = random.choice(self.user_agents)
        request.headers['User-Agent'] = ua
        
        # Add more browser-like headers
        request.headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
        })
        
        # Add referer for some requests
        if random.random() > 0.5:
            domain = urlparse(request.url).netloc
            request.headers['Referer'] = f'https://{domain}/'


class SmartRetryMiddleware(RetryMiddleware):
    """
    Enhanced retry middleware with backoff and proxy rotation
    """
    
    def process_response(self, request, response, spider):
        """Handle responses that might indicate blocking"""
        
        # Check for blocking indicators
        blocking_indicators = [
            response.status == 403,
            response.status == 429,
            'captcha' in response.url.lower(),
            'blocked' in response.text.lower() if hasattr(response, 'text') else False,
            len(response.body) < 500,  # Suspiciously small response
        ]
        
        if any(blocking_indicators):
            spider.logger.warning(f'Possible blocking detected: {response.status} - {response.url}')
            
            # Force proxy rotation
            request.meta['retry_times'] = request.meta.get('retry_times', 0) + 1
            
            # Add delay
            request.meta['download_delay'] = min(
                request.meta.get('download_delay', 1) * 2,
                30  # Max 30 second delay
            )
            
            return self._retry(request, response.status, spider) or response
        
        return super().process_response(request, response, spider)


class CloudflareBypassMiddleware:
    """
    Basic Cloudflare bypass techniques
    """
    
    def process_request(self, request, spider):
        """Add Cloudflare bypass headers"""
        request.headers.update({
            'sec-ch-ua': '"Chromium";v="120", "Not(A:Brand";v="24", "Google Chrome";v="120"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
        })


class RequestFingerprintMiddleware:
    """
    Randomize request fingerprint to avoid detection
    """
    
    def process_request(self, request, spider):
        """Randomize various request parameters"""
        
        # Random accept-language
        languages = [
            'en-US,en;q=0.9',
            'en-GB,en;q=0.9',
            'en-US,en;q=0.9,es;q=0.8',
            'en-US,en;q=0.9,fr;q=0.8',
        ]
        request.headers['Accept-Language'] = random.choice(languages)
        
        # Random viewport hints
        if random.random() > 0.5:
            request.headers['Viewport-Width'] = random.choice(['1920', '1366', '1440', '1536'])
            request.headers['DPR'] = random.choice(['1', '1.25', '1.5', '2'])


# Free proxy services that provide API access
class FreeProxyAPIMiddleware:
    """
    Use free proxy APIs with rotation
    """
    
    PROXY_APIS = [
        {
            'name': 'ProxyScrape',
            'url': 'https://api.proxyscrape.com/v2/',
            'params': {
                'request': 'get',
                'protocol': 'http',
                'timeout': '10000',
                'country': 'all',
                'ssl': 'all',
                'anonymity': 'all',
                'format': 'json'
            }
        }
    ]
    
    def __init__(self):
        self.proxies = []
        self.current_index = 0
        
    @classmethod
    def from_crawler(cls, crawler):
        return cls()
    
    def process_request(self, request, spider):
        """Add proxy from free API"""
        if not self.proxies:
            self._fetch_proxies()
        
        if self.proxies:
            proxy = self.proxies[self.current_index % len(self.proxies)]
            self.current_index += 1
            request.meta['proxy'] = f"http://{proxy}"
    
    def _fetch_proxies(self):
        """Fetch proxies from free APIs"""
        for api in self.PROXY_APIS:
            try:
                response = requests.get(api['url'], params=api['params'], timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    for proxy in data[:20]:  # Limit to 20 proxies
                        if isinstance(proxy, dict):
                            self.proxies.append(f"{proxy.get('ip')}:{proxy.get('port')}")
            except Exception as e:
                print(f"Failed to fetch from {api['name']}: {e}")
