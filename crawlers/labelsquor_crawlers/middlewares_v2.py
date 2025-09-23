"""
Generic anti-blocking middlewares using retailer strategies
This replaces the old middlewares.py with a more flexible approach
"""
import random
import requests
from scrapy import signals
from scrapy.downloadermiddlewares.retry import RetryMiddleware
from scrapy.exceptions import NotConfigured, IgnoreRequest
from typing import List, Dict, Optional
import json
from urllib.parse import urlparse
import time

from .antiblock.base import RetailerAntiBlockRegistry
from .antiblock.retailers import *  # Import all retailer strategies


class GenericAntiBlockMiddleware:
    """
    Main middleware that applies retailer-specific anti-blocking strategies
    """
    
    def __init__(self, crawler):
        self.crawler = crawler
        self.strategies = {}
        self.stats = crawler.stats
        
        # Load proxy pools
        self.proxy_pools = {
            'free': [],
            'proxyscrape': [],
            'premium': [],  # For future premium proxy integration
        }
        self._init_proxy_pools()
    
    @classmethod
    def from_crawler(cls, crawler):
        middleware = cls(crawler)
        crawler.signals.connect(middleware.spider_opened, signal=signals.spider_opened)
        return middleware
    
    def spider_opened(self, spider):
        """Initialize when spider opens"""
        # Get retailer from spider name or attribute
        retailer = getattr(spider, 'retailer', None)
        if not retailer:
            # Try to infer from spider name
            for r in ['bigbasket', 'amazon', 'flipkart', 'blinkit', 'zepto']:
                if r in spider.name.lower():
                    retailer = r
                    break
        
        if retailer:
            spider.logger.info(f"Loading anti-block strategy for {retailer}")
            strategy = RetailerAntiBlockRegistry.get_strategy(retailer)
            self.strategies[spider.name] = strategy
    
    def process_request(self, request, spider):
        """Apply anti-blocking measures to request"""
        strategy = self.strategies.get(spider.name)
        if not strategy or not strategy.enabled:
            return None
        
        # Apply user agent
        user_agents = strategy.get_user_agents()
        if user_agents:
            request.headers['User-Agent'] = random.choice(user_agents)
        
        # Apply headers
        headers = strategy.get_headers(request)
        for key, value in headers.items():
            request.headers[key] = value
        
        # Apply proxy
        if strategy.should_use_proxy(request):
            proxy = self._get_proxy(strategy)
            if proxy:
                request.meta['proxy'] = proxy
                spider.logger.debug(f"Using proxy: {proxy}")
                self.stats.inc_value('antiblock/proxy_used')
        
        # Apply delay
        delay = strategy.get_download_delay()
        request.meta['download_delay'] = delay
        
        # Track requests
        self.stats.inc_value(f'antiblock/{spider.name}/requests')
    
    def process_response(self, request, response, spider):
        """Check for blocking and handle accordingly"""
        strategy = self.strategies.get(spider.name)
        if not strategy:
            return response
        
        # Check if blocked
        if strategy.handle_blocking_response(response):
            self.stats.inc_value(f'antiblock/{spider.name}/blocked')
            spider.logger.warning(f"Blocking detected for {response.url}")
            
            # Get retry policy
            retry_policy = strategy.get_retry_policy()
            retry_times = request.meta.get('retry_times', 0)
            
            if retry_times < retry_policy['retry_times']:
                # Calculate backoff
                backoff = min(
                    retry_policy['backoff_base'] ** retry_times,
                    retry_policy['backoff_max']
                )
                
                spider.logger.info(f"Retrying {response.url} after {backoff}s (attempt {retry_times + 1})")
                
                # Create retry request
                retry_request = request.copy()
                retry_request.meta['retry_times'] = retry_times + 1
                retry_request.dont_filter = True
                
                # Force new proxy
                if strategy.should_use_proxy(request):
                    retry_request.meta['proxy'] = self._get_proxy(strategy, exclude=request.meta.get('proxy'))
                
                # Schedule with delay
                self.crawler.engine.download(retry_request, spider)
                
                raise IgnoreRequest(f"Blocked response, retrying with backoff")
        
        self.stats.inc_value(f'antiblock/{spider.name}/success')
        return response
    
    def process_exception(self, request, exception, spider):
        """Handle exceptions, particularly proxy failures"""
        strategy = self.strategies.get(spider.name)
        if not strategy:
            return None
        
        if 'proxy' in request.meta:
            proxy = request.meta['proxy']
            spider.logger.warning(f"Proxy {proxy} failed: {exception}")
            self._mark_proxy_failed(proxy)
            self.stats.inc_value(f'antiblock/{spider.name}/proxy_failed')
            
            # Retry with different proxy
            retry_policy = strategy.get_retry_policy()
            retry_times = request.meta.get('retry_times', 0)
            
            if retry_times < retry_policy.get('proxy_retry_count', 3):
                retry_request = request.copy()
                retry_request.meta['retry_times'] = retry_times + 1
                retry_request.meta['proxy'] = self._get_proxy(strategy, exclude=proxy)
                retry_request.dont_filter = True
                return retry_request
    
    def _init_proxy_pools(self):
        """Initialize proxy pools from various sources"""
        # Free proxy sources
        free_sources = [
            'https://api.proxyscrape.com/v2/?request=get&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all&simplified=true',
            'https://www.proxy-list.download/api/v1/get?type=http',
            'https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt',
        ]
        
        for source in free_sources:
            try:
                response = requests.get(source, timeout=10)
                if response.status_code == 200:
                    if 'proxyscrape' in source:
                        pool_name = 'proxyscrape'
                    else:
                        pool_name = 'free'
                    
                    # Parse based on content type
                    if 'json' in response.headers.get('content-type', ''):
                        data = response.json()
                        if isinstance(data, list):
                            for item in data[:30]:  # Limit per source
                                if isinstance(item, dict) and 'ip' in item:
                                    proxy = f"http://{item['ip']}:{item.get('port', 80)}"
                                    self.proxy_pools[pool_name].append({
                                        'url': proxy,
                                        'failures': 0,
                                        'last_used': 0
                                    })
                    else:
                        # Plain text format
                        lines = response.text.strip().split('\n')
                        for line in lines[:30]:  # Limit per source
                            if line.strip():
                                proxy = f"http://{line.strip()}"
                                self.proxy_pools[pool_name].append({
                                    'url': proxy,
                                    'failures': 0,
                                    'last_used': 0
                                })
            except Exception as e:
                print(f"Failed to load proxies from {source}: {e}")
        
        total_proxies = sum(len(pool) for pool in self.proxy_pools.values())
        print(f"Loaded {total_proxies} proxies across all pools")
    
    def _get_proxy(self, strategy, exclude=None):
        """Get a proxy based on strategy configuration"""
        config = strategy.get_proxy_config()
        providers = config.get('providers', ['free'])
        
        # Collect available proxies
        available_proxies = []
        for provider in providers:
            pool = self.proxy_pools.get(provider, [])
            for proxy in pool:
                # Skip failed proxies
                if proxy['failures'] >= 3:
                    continue
                # Skip recently used
                if time.time() - proxy['last_used'] < 60:
                    continue
                # Skip excluded
                if exclude and proxy['url'] == exclude:
                    continue
                available_proxies.append(proxy)
        
        if not available_proxies:
            # Reset some proxies if all failed
            for provider in providers:
                pool = self.proxy_pools.get(provider, [])
                for proxy in pool:
                    if proxy['failures'] > 0:
                        proxy['failures'] = 0
            return None
        
        # Select proxy
        proxy_info = random.choice(available_proxies)
        proxy_info['last_used'] = time.time()
        
        return proxy_info['url']
    
    def _mark_proxy_failed(self, proxy_url):
        """Mark a proxy as failed"""
        for pool in self.proxy_pools.values():
            for proxy in pool:
                if proxy['url'] == proxy_url:
                    proxy['failures'] += 1
                    break


class SmartRetryMiddleware(RetryMiddleware):
    """
    Enhanced retry middleware that works with anti-block strategies
    """
    
    def __init__(self, settings):
        super().__init__(settings)
        self.strategies = {}
    
    def process_response(self, request, response, spider):
        """Use strategy-specific retry logic"""
        # Get strategy
        strategy = None
        if hasattr(spider, 'antiblock_strategy'):
            strategy = spider.antiblock_strategy
        elif hasattr(spider, 'retailer'):
            strategy = RetailerAntiBlockRegistry.get_strategy(spider.retailer)
        
        if strategy:
            # Check if should retry based on strategy
            retry_policy = strategy.get_retry_policy()
            if response.status in retry_policy.get('retry_codes', []):
                return self._retry(request, response.reason, spider) or response
        
        return super().process_response(request, response, spider)


class AdaptiveDelayMiddleware:
    """
    Dynamically adjust delays based on response patterns
    """
    
    def __init__(self, crawler):
        self.crawler = crawler
        self.delay_adjustments = {}
        self.window_size = 20  # Track last N responses
        self.response_times = {}
    
    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler)
    
    def process_request(self, request, spider):
        """Apply adaptive delay"""
        domain = urlparse(request.url).netloc
        
        # Get current adjustment factor
        adjustment = self.delay_adjustments.get(domain, 1.0)
        
        # Apply to download delay
        base_delay = request.meta.get('download_delay', 1.0)
        request.meta['download_delay'] = base_delay * adjustment
        
        # Record request time
        request.meta['adaptive_delay_start'] = time.time()
    
    def process_response(self, request, response, spider):
        """Analyze response and adjust delays"""
        domain = urlparse(request.url).netloc
        
        # Initialize tracking
        if domain not in self.response_times:
            self.response_times[domain] = []
        
        # Record response time
        if 'adaptive_delay_start' in request.meta:
            response_time = time.time() - request.meta['adaptive_delay_start']
            self.response_times[domain].append({
                'time': response_time,
                'status': response.status,
                'size': len(response.body)
            })
            
            # Keep window size
            if len(self.response_times[domain]) > self.window_size:
                self.response_times[domain].pop(0)
            
            # Analyze patterns
            self._adjust_delay(domain, spider)
        
        return response
    
    def _adjust_delay(self, domain, spider):
        """Adjust delay based on response patterns"""
        responses = self.response_times[domain]
        if len(responses) < 5:
            return
        
        # Calculate metrics
        recent = responses[-5:]
        error_rate = sum(1 for r in recent if r['status'] >= 400) / len(recent)
        avg_time = sum(r['time'] for r in recent) / len(recent)
        
        # Current adjustment
        current = self.delay_adjustments.get(domain, 1.0)
        
        # Adjust based on patterns
        if error_rate > 0.5:
            # High error rate, increase delay
            new_adjustment = min(current * 1.5, 5.0)
            spider.logger.info(f"Increasing delay for {domain}: {new_adjustment}x")
        elif error_rate == 0 and avg_time < 1.0:
            # No errors and fast responses, can decrease delay
            new_adjustment = max(current * 0.8, 0.5)
            spider.logger.info(f"Decreasing delay for {domain}: {new_adjustment}x")
        else:
            new_adjustment = current
        
        self.delay_adjustments[domain] = new_adjustment
