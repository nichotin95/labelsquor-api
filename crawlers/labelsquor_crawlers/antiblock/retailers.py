"""
Retailer-specific anti-blocking strategies
"""
from typing import Dict, List, Any
from scrapy.http import Request, Response
from .base import BaseAntiBlockStrategy, RetailerAntiBlockRegistry


class BigBasketAntiBlockStrategy(BaseAntiBlockStrategy):
    """
    Anti-blocking strategy specific to BigBasket
    """
    
    def get_user_agents(self) -> List[str]:
        """BigBasket prefers Chrome and mobile user agents"""
        return [
            # Desktop Chrome (most common)
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            
            # Mobile (BigBasket has good mobile support)
            'Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
            'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
        ]
    
    def get_headers(self, request: Request) -> Dict[str, str]:
        """BigBasket-specific headers"""
        headers = super().get_headers(request)
        
        # BigBasket specific headers
        headers.update({
            'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'none',
            'sec-fetch-user': '?1',
        })
        
        # Add referer for category/search pages
        if '/pc/' in request.url or '/ps/' in request.url:
            headers['Referer'] = 'https://www.bigbasket.com/'
        
        return headers
    
    def should_use_proxy(self, request: Request) -> bool:
        """Always use proxy for BigBasket on cloud platforms"""
        # BigBasket aggressively blocks cloud IPs
        return True
    
    def handle_blocking_response(self, response: Response) -> bool:
        """BigBasket-specific blocking detection"""
        # Check base indicators
        if super().handle_blocking_response(response):
            return True
        
        # BigBasket specific patterns
        blocking_patterns = [
            'access denied',
            'please verify you are human',
            'suspicious activity',
            'temporarily blocked',
        ]
        
        response_text = response.text.lower()
        return any(pattern in response_text for pattern in blocking_patterns)
    
    def get_retry_policy(self) -> Dict[str, Any]:
        """BigBasket needs more aggressive retries"""
        return {
            'retry_times': 5,
            'retry_codes': [403, 429, 500, 502, 503, 504, 408],
            'backoff_base': 3,  # More aggressive backoff
            'backoff_max': 120,
        }


class AmazonAntiBlockStrategy(BaseAntiBlockStrategy):
    """
    Anti-blocking strategy for Amazon India
    """
    
    def get_user_agents(self) -> List[str]:
        """Amazon prefers standard desktop browsers"""
        return [
            # Windows Chrome (most common for Amazon)
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            
            # Windows Firefox
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0',
            
            # Mac Safari (also common)
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
        ]
    
    def get_headers(self, request: Request) -> Dict[str, str]:
        """Amazon-specific headers"""
        headers = super().get_headers(request)
        
        # Amazon specific headers
        headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7',  # India specific
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Pragma': 'no-cache',
        })
        
        # Amazon tracks session consistency
        if 'amazon.in' in request.url:
            headers['Host'] = 'www.amazon.in'
        
        return headers
    
    def should_use_proxy(self, request: Request) -> bool:
        """Amazon requires careful proxy usage"""
        # Use proxy for product/search pages, not for images
        if any(path in request.url for path in ['/dp/', '/s?', '/gp/']):
            return True
        return False
    
    def handle_blocking_response(self, response: Response) -> bool:
        """Amazon-specific blocking detection"""
        if super().handle_blocking_response(response):
            return True
        
        # Amazon specific patterns
        blocking_patterns = [
            'sorry, we just need to make sure you\'re not a robot',
            'enter the characters you see below',
            'to discuss automated access',
            'amazon captcha',
            'api-services-support@amazon.com',
        ]
        
        response_text = response.text.lower()
        return any(pattern in response_text for pattern in blocking_patterns)
    
    def get_retry_policy(self) -> Dict[str, Any]:
        """Amazon needs careful retry strategy"""
        return {
            'retry_times': 3,  # Don't retry too much
            'retry_codes': [503, 500, 502, 504],  # Don't retry 403/429
            'backoff_base': 5,
            'backoff_max': 300,  # Long backoff
        }


class FlipkartAntiBlockStrategy(BaseAntiBlockStrategy):
    """
    Anti-blocking strategy for Flipkart
    """
    
    def get_headers(self, request: Request) -> Dict[str, str]:
        """Flipkart-specific headers"""
        headers = super().get_headers(request)
        
        # Flipkart uses specific API headers
        headers.update({
            'X-User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 FKUA/website/42/website/Desktop',
            'Accept': '*/*',
        })
        
        return headers
    
    def handle_blocking_response(self, response: Response) -> bool:
        """Flipkart-specific blocking detection"""
        if super().handle_blocking_response(response):
            return True
        
        # Flipkart returns JSON errors
        try:
            if response.headers.get('Content-Type', '').startswith('application/json'):
                data = response.json()
                if data.get('ERROR') or data.get('error'):
                    return True
        except:
            pass
        
        return False


class BlinkitAntiBlockStrategy(BaseAntiBlockStrategy):
    """
    Anti-blocking strategy for Blinkit
    """
    
    def get_headers(self, request: Request) -> Dict[str, str]:
        """Blinkit-specific headers"""
        headers = super().get_headers(request)
        
        # Blinkit is mobile-first
        headers.update({
            'X-Requested-With': 'XMLHttpRequest',
            'Accept': 'application/json, text/plain, */*',
        })
        
        return headers
    
    def should_use_proxy(self, request: Request) -> bool:
        """Blinkit is less aggressive about blocking"""
        # Only use proxy if explicitly configured
        return self.config.get('force_proxy', False)


class ZeptoAntiBlockStrategy(BaseAntiBlockStrategy):
    """
    Anti-blocking strategy for Zepto
    """
    
    def get_user_agents(self) -> List[str]:
        """Zepto is primarily mobile"""
        return [
            # Mobile browsers
            'Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
            'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
            # Some desktop
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        ]
    
    def get_headers(self, request: Request) -> Dict[str, str]:
        """Zepto-specific headers"""
        headers = super().get_headers(request)
        
        # Zepto uses app-like headers
        headers.update({
            'X-Platform': 'web',
            'X-Client-Version': '1.0.0',
        })
        
        return headers


# Register all strategies
RetailerAntiBlockRegistry.register('bigbasket', BigBasketAntiBlockStrategy)
RetailerAntiBlockRegistry.register('amazon', AmazonAntiBlockStrategy)
RetailerAntiBlockRegistry.register('amazon.in', AmazonAntiBlockStrategy)
RetailerAntiBlockRegistry.register('flipkart', FlipkartAntiBlockStrategy)
RetailerAntiBlockRegistry.register('blinkit', BlinkitAntiBlockStrategy)
RetailerAntiBlockRegistry.register('zepto', ZeptoAntiBlockStrategy)
