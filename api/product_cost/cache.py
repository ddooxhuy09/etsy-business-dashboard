"""
Simple in-memory cache with TTL.
"""
from typing import Dict, Any, Optional
from datetime import datetime, timedelta


class SimpleCache:
    """Simple in-memory cache with TTL."""
    
    def __init__(self, ttl_seconds: int = 300):  # 5 minutes default
        self._cache: Dict[str, tuple] = {}
        self._ttl = ttl_seconds
    
    def get(self, key: str) -> Optional[Any]:
        if key in self._cache:
            data, timestamp = self._cache[key]
            if datetime.now() - timestamp < timedelta(seconds=self._ttl):
                return data
            else:
                del self._cache[key]
        return None
    
    def set(self, key: str, value: Any):
        self._cache[key] = (value, datetime.now())
    
    def clear(self):
        self._cache.clear()


# Cache instances - longer TTL since product cost data doesn't change frequently
products_cache = SimpleCache(ttl_seconds=1800)  # 30 min cache for main products list
variants_cache = SimpleCache(ttl_seconds=1800)  # 30 min cache
cogs_cache = SimpleCache(ttl_seconds=1800)
etsy_fee_cache = SimpleCache(ttl_seconds=1800)
margin_cache = SimpleCache(ttl_seconds=1800)
