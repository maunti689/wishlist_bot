import asyncio
from typing import Optional

import redis.asyncio as redis_async

from config import REDIS_URL

_redis_instance: Optional[redis_async.Redis] = None
_lock = asyncio.Lock()


async def get_redis_connection() -> redis_async.Redis:
    global _redis_instance
    if _redis_instance is None:
        async with _lock:
            if _redis_instance is None:
                _redis_instance = redis_async.from_url(REDIS_URL)
    return _redis_instance


async def ensure_redis_connection() -> redis_async.Redis:
    redis = await get_redis_connection()
    await redis.ping()
    return redis


async def close_redis_connection() -> None:
    global _redis_instance
    if _redis_instance is not None:
        await _redis_instance.close()
        _redis_instance = None
