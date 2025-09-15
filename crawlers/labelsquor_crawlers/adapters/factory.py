"""
Factory for creating retailer adapters
"""
from typing import Dict, Type
from .base import RetailerAdapter
from .bigbasket import BigBasketAdapter
from .blinkit import BlinkitAdapter


class RetailerAdapterFactory:
    """Factory for creating retailer-specific adapters"""
    
    # Registry of available adapters
    _adapters: Dict[str, Type[RetailerAdapter]] = {
        'bigbasket': BigBasketAdapter,
        'blinkit': BlinkitAdapter,
    }
    
    @classmethod
    def register_adapter(cls, name: str, adapter_class: Type[RetailerAdapter]):
        """Register a new adapter"""
        cls._adapters[name.lower()] = adapter_class
    
    @classmethod
    def get_adapter(cls, retailer: str) -> RetailerAdapter:
        """Get adapter instance for a retailer"""
        retailer_lower = retailer.lower()
        
        if retailer_lower not in cls._adapters:
            raise ValueError(f"No adapter found for retailer: {retailer}")
        
        adapter_class = cls._adapters[retailer_lower]
        return adapter_class()
    
    @classmethod
    def get_supported_retailers(cls) -> list:
        """Get list of supported retailers"""
        return list(cls._adapters.keys())
    
    @classmethod
    def is_supported(cls, retailer: str) -> bool:
        """Check if a retailer is supported"""
        return retailer.lower() in cls._adapters
