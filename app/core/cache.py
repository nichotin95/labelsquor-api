"""
Advanced caching with Redis and in-memory fallback
"""

import hashlib
import json
from abc import ABC, abstractmethod
from datetime import timedelta
from functools import wraps
from typing import Any, Callable, Optional, Union

import orjson
from aiocache import Cache, caches
from aiocache.serializers import BaseSerializer
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.logging import log


class OrjsonSerializer(BaseSerializer):
    """Fast JSON serializer using orjson"""

    def dumps(self, value: Any) -> bytes:
        return orjson.dumps(value)

    def loads(self, value: bytes) -> Any:
        return orjson.loads(value)


class CacheBackend(ABC):
    """Abstract cache backend"""

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        pass

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        pass

    @abstractmethod
    async def clear(self, namespace: Optional[str] = None) -> bool:
        pass


class RedisCache(CacheBackend):
    """Redis cache backend with connection pooling"""

    def __init__(self):
        if not settings.REDIS_URL:
            raise ValueError("REDIS_URL not configured")

        caches.set_config(
            {
                "default": {
                    "cache": "aiocache.RedisCache",
                    "endpoint": settings.REDIS_URL.split("://")[1].split(":")[0],
                    "port": int(settings.REDIS_URL.split(":")[-1].split("/")[0]),
                    "serializer": {"class": "app.core.cache.OrjsonSerializer"},
                    "timeout": 1,
                    "pool_min_size": 1,
                    "pool_max_size": 10,
                }
            }
        )
        self.cache = caches.get("default")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=5))
    async def get(self, key: str) -> Optional[Any]:
        try:
            return await self.cache.get(key)
        except Exception as e:
            log.warning(f"Redis get failed for key {key}", error=str(e))
            return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        try:
            return await self.cache.set(key, value, ttl=ttl)
        except Exception as e:
            log.warning(f"Redis set failed for key {key}", error=str(e))
            return False

    async def delete(self, key: str) -> bool:
        try:
            return await self.cache.delete(key)
        except Exception as e:
            log.warning(f"Redis delete failed for key {key}", error=str(e))
            return False

    async def exists(self, key: str) -> bool:
        try:
            return await self.cache.exists(key)
        except Exception as e:
            log.warning(f"Redis exists failed for key {key}", error=str(e))
            return False

    async def clear(self, namespace: Optional[str] = None) -> bool:
        try:
            if namespace:
                return await self.cache.clear(namespace=namespace)
            return await self.cache.clear()
        except Exception as e:
            log.warning("Redis clear failed", error=str(e))
            return False


class InMemoryCache(CacheBackend):
    """In-memory cache fallback using aiocache"""

    def __init__(self):
        self.cache = Cache(Cache.MEMORY, serializer=OrjsonSerializer())

    async def get(self, key: str) -> Optional[Any]:
        return await self.cache.get(key)

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        return await self.cache.set(key, value, ttl=ttl)

    async def delete(self, key: str) -> bool:
        return await self.cache.delete(key)

    async def exists(self, key: str) -> bool:
        return await self.cache.exists(key)

    async def clear(self, namespace: Optional[str] = None) -> bool:
        return await self.cache.clear(namespace=namespace)


# Global cache instance
_cache: Optional[CacheBackend] = None


def get_cache() -> CacheBackend:
    """Get cache backend instance"""
    global _cache

    if _cache is None:
        if settings.REDIS_URL:
            try:
                _cache = RedisCache()
                log.info("Using Redis cache backend")
            except Exception as e:
                log.warning(f"Failed to initialize Redis cache: {e}, falling back to in-memory")
                _cache = InMemoryCache()
        else:
            _cache = InMemoryCache()
            log.info("Using in-memory cache backend")

    return _cache


def cache_key(*args, **kwargs) -> str:
    """
    Generate cache key from arguments

    Examples:
        cache_key("user", 123) -> "user:123"
        cache_key("product", id=456, version=2) -> "product:id=456:version=2"
    """
    parts = [str(arg) for arg in args]
    parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
    return ":".join(parts)


def cache_key_hash(*args, **kwargs) -> str:
    """Generate hashed cache key for long keys"""
    key = cache_key(*args, **kwargs)
    if len(key) > 200:  # Redis key length limit is 512MB, but we'll be conservative
        # Use hash for long keys
        hash_digest = hashlib.sha256(key.encode()).hexdigest()[:16]
        return f"hash:{hash_digest}"
    return key


def cached(
    ttl: Union[int, timedelta] = None,
    key_prefix: Optional[str] = None,
    key_builder: Optional[Callable] = None,
    condition: Optional[Callable] = None,
    namespace: Optional[str] = None,
):
    """
    Decorator for caching function results

    Args:
        ttl: Time to live in seconds or timedelta
        key_prefix: Prefix for cache keys
        key_builder: Custom key builder function
        condition: Function to determine if result should be cached
        namespace: Cache namespace for easy clearing

    Example:
        @cached(ttl=300, key_prefix="user")
        async def get_user(user_id: int):
            return await db.get_user(user_id)
    """
    if isinstance(ttl, timedelta):
        ttl = int(ttl.total_seconds())

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache = get_cache()

            # Build cache key
            if key_builder:
                key = key_builder(*args, **kwargs)
            else:
                # Default key building
                func_name = func.__name__
                key_parts = [key_prefix or func_name]

                # Add args and kwargs to key
                if args:
                    key_parts.extend(str(arg) for arg in args)
                if kwargs:
                    key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))

                key = cache_key_hash(*key_parts)

            # Add namespace if provided
            if namespace:
                key = f"{namespace}:{key}"

            # Try to get from cache
            cached_value = await cache.get(key)
            if cached_value is not None:
                log.debug(f"Cache hit for {key}")
                return cached_value

            # Call function
            result = await func(*args, **kwargs)

            # Check condition
            if condition and not condition(result):
                return result

            # Cache result
            cache_ttl = ttl or settings.CACHE_TTL
            await cache.set(key, result, ttl=cache_ttl)
            log.debug(f"Cached {key} for {cache_ttl}s")

            return result

        # Add cache control methods
        wrapper.invalidate = lambda *args, **kwargs: _invalidate_cache(
            func, key_prefix, key_builder, namespace, *args, **kwargs
        )
        wrapper.refresh = lambda *args, **kwargs: _refresh_cache(func, wrapper, *args, **kwargs)

        return wrapper

    return decorator


async def _invalidate_cache(
    func: Callable,
    key_prefix: Optional[str],
    key_builder: Optional[Callable],
    namespace: Optional[str],
    *args,
    **kwargs,
) -> bool:
    """Invalidate cached value"""
    cache = get_cache()

    if key_builder:
        key = key_builder(*args, **kwargs)
    else:
        func_name = func.__name__
        key_parts = [key_prefix or func_name]
        if args:
            key_parts.extend(str(arg) for arg in args)
        if kwargs:
            key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
        key = cache_key_hash(*key_parts)

    if namespace:
        key = f"{namespace}:{key}"

    return await cache.delete(key)


async def _refresh_cache(func: Callable, wrapper: Callable, *args, **kwargs) -> Any:
    """Force refresh cached value"""
    # First invalidate
    await wrapper.invalidate(*args, **kwargs)
    # Then call to repopulate
    return await wrapper(*args, **kwargs)


# Utility class for easy cache key management
class CacheKey:
    """Cache key builder with fluent interface"""

    def __init__(self, *parts):
        self.parts = list(parts)

    def add(self, *parts) -> "CacheKey":
        self.parts.extend(parts)
        return self

    def with_prefix(self, prefix: str) -> "CacheKey":
        self.parts.insert(0, prefix)
        return self

    def with_namespace(self, namespace: str) -> "CacheKey":
        return CacheKey(namespace, *self.parts)

    def build(self) -> str:
        return cache_key(*self.parts)

    async def get(self) -> Optional[Any]:
        cache = get_cache()
        return await cache.get(self.build())

    async def set(self, value: Any, ttl: Optional[int] = None) -> bool:
        cache = get_cache()
        return await cache.set(self.build(), value, ttl=ttl)

    async def delete(self) -> bool:
        cache = get_cache()
        return await cache.delete(self.build())

    async def exists(self) -> bool:
        cache = get_cache()
        return await cache.exists(self.build())


# Export convenience function
cache_key = CacheKey
