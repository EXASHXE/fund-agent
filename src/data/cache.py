"""内存缓存 — 避免同一次运行中重复拉取相同数据"""
from typing import Dict, Optional
from datetime import datetime


class DataCache:
    """简单的内存缓存，TTL 默认 5 分钟"""

    def __init__(self, ttl_seconds: int = 300):
        self._cache: Dict[str, tuple] = {}
        self._ttl = ttl_seconds

    def get(self, key: str) -> Optional[object]:
        if key in self._cache:
            value, timestamp = self._cache[key]
            if (datetime.now() - timestamp).total_seconds() < self._ttl:
                return value
            del self._cache[key]
        return None

    def set(self, key: str, value: object):
        self._cache[key] = (value, datetime.now())

    def invalidate(self, key: str = None):
        if key:
            self._cache.pop(key, None)
        else:
            self._cache.clear()


_cache = DataCache()


def cached_fetch(fetch_fn, symbol: str, *args, **kwargs):
    """带缓存的数据获取包装"""
    cache_key = f"{fetch_fn.__name__}:{symbol}:{args}:{kwargs}"
    result = _cache.get(cache_key)
    if result is not None:
        return result
    result = fetch_fn(symbol, *args, **kwargs)
    _cache.set(cache_key, result)
    return result
