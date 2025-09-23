"""
Base classes for anti-blocking strategies
Provides a flexible framework for retailer-specific anti-blocking measures
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
import random
import json
from scrapy.http import Request, Response
from scrapy import Spider


class AntiBlockStrategy(ABC):
    """
    Abstract base class for anti-blocking strategies
    Each retailer can have its own implementation
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.enabled = config.get('enabled', True)
        
    @abstractmethod
    def get_user_agents(self) -> List[str]:
        """Return list of user agents for this retailer"""
        pass
    
    @abstractmethod
    def get_headers(self, request: Request) -> Dict[str, str]:
        """Return headers specific to this retailer"""
        pass
    
    @abstractmethod
    def should_use_proxy(self, request: Request) -> bool:
        """Determine if proxy should be used for this request"""
        pass
    
    @abstractmethod
    def get_proxy_config(self) -> Dict[str, Any]:
        """Return proxy configuration for this retailer"""
        pass
    
    @abstractmethod
    def handle_blocking_response(self, response: Response) -> bool:
        """Check if response indicates blocking"""
        pass
    
    @abstractmethod
    def get_retry_policy(self) -> Dict[str, Any]:
        """Return retry policy for this retailer"""
        pass
    
    def get_download_delay(self) -> float:
        """Get download delay for this retailer"""
        base_delay = self.config.get('download_delay', 1.0)
        randomization = self.config.get('delay_randomization', 0.5)
        return base_delay + (random.random() * randomization * base_delay)


class BaseAntiBlockStrategy(AntiBlockStrategy):
    """
    Default implementation with common anti-blocking measures
    """
    
    # Common desktop user agents
    DEFAULT_USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:120.0) Gecko/20100101 Firefox/120.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
    ]
    
    def get_user_agents(self) -> List[str]:
        """Return custom user agents or defaults"""
        return self.config.get('user_agents', self.DEFAULT_USER_AGENTS)
    
    def get_headers(self, request: Request) -> Dict[str, str]:
        """Return browser-like headers"""
        headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': random.choice([
                'en-US,en;q=0.9',
                'en-GB,en;q=0.9',
                'en-US,en;q=0.9,hi;q=0.8',  # Include Hindi for Indian sites
            ]),
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
        }
        
        # Add custom headers from config
        custom_headers = self.config.get('custom_headers', {})
        headers.update(custom_headers)
        
        return headers
    
    def should_use_proxy(self, request: Request) -> bool:
        """Use proxy based on configuration"""
        # Always use proxy in cloud environments
        if self.config.get('force_proxy', False):
            return True
        
        # Skip proxy for local/staging environments
        if any(host in request.url for host in ['localhost', '127.0.0.1', 'staging']):
            return False
        
        # Use proxy probability from config
        proxy_probability = self.config.get('proxy_probability', 1.0)
        return random.random() < proxy_probability
    
    def get_proxy_config(self) -> Dict[str, Any]:
        """Return proxy configuration"""
        return {
            'type': self.config.get('proxy_type', 'rotating'),
            'providers': self.config.get('proxy_providers', ['free']),
            'timeout': self.config.get('proxy_timeout', 30),
            'retry_count': self.config.get('proxy_retry_count', 3),
        }
    
    def handle_blocking_response(self, response: Response) -> bool:
        """Check common blocking indicators"""
        blocking_indicators = [
            response.status in [403, 429, 503],
            len(response.body) < 500,
        ]
        
        # Check for custom blocking patterns
        blocking_patterns = self.config.get('blocking_patterns', [])
        for pattern in blocking_patterns:
            if pattern.lower() in response.text.lower():
                blocking_indicators.append(True)
                break
        
        return any(blocking_indicators)
    
    def get_retry_policy(self) -> Dict[str, Any]:
        """Return retry configuration"""
        return {
            'retry_times': self.config.get('retry_times', 3),
            'retry_codes': self.config.get('retry_codes', [500, 502, 503, 504, 408, 429, 403]),
            'backoff_base': self.config.get('backoff_base', 2),
            'backoff_max': self.config.get('backoff_max', 60),
        }


class RetailerAntiBlockRegistry:
    """
    Registry for retailer-specific anti-blocking strategies
    """
    
    _strategies: Dict[str, type] = {}
    _instances: Dict[str, AntiBlockStrategy] = {}
    
    @classmethod
    def register(cls, retailer: str, strategy_class: type):
        """Register a strategy for a retailer"""
        cls._strategies[retailer.lower()] = strategy_class
    
    @classmethod
    def get_strategy(cls, retailer: str, config: Optional[Dict] = None) -> AntiBlockStrategy:
        """Get strategy instance for a retailer"""
        retailer_lower = retailer.lower()
        
        # Return cached instance if no new config
        if retailer_lower in cls._instances and config is None:
            return cls._instances[retailer_lower]
        
        # Create new instance
        strategy_class = cls._strategies.get(retailer_lower, BaseAntiBlockStrategy)
        
        # Load config from file if not provided
        if config is None:
            config = cls._load_config(retailer)
        
        instance = strategy_class(config)
        cls._instances[retailer_lower] = instance
        
        return instance
    
    @classmethod
    def _load_config(cls, retailer: str) -> Dict[str, Any]:
        """Load configuration for a retailer"""
        try:
            import os
            config_path = os.path.join(
                os.path.dirname(__file__),
                'configs',
                f'{retailer.lower()}.json'
            )
            
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception:
            # Return default config if file not found
            return {
                'enabled': True,
                'download_delay': 1.0,
                'proxy_probability': 1.0,
                'retry_times': 3,
            }
