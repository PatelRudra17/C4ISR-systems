import json
import redis.asyncio as redis
from typing import Any, Dict, List, Optional
from app.core.config import get_settings

settings = get_settings()

# Redis connection pool
redis_pool = redis.ConnectionPool.from_url(
    settings.REDIS_URL,
    decode_responses=True,
    max_connections=50
)


async def get_redis() -> redis.Redis:
    """Get Redis client from pool"""
    return redis.Redis(connection_pool=redis_pool)


# Cache Operations
async def cache_set(key: str, value: Any, ttl: int = 300):
    """Set cache with TTL"""
    r = await get_redis()
    await r.setex(key, ttl, json.dumps(value))
    await r.close()


async def cache_get(key: str) -> Optional[Any]:
    """Get cached value"""
    r = await get_redis()
    value = await r.get(key)
    await r.close()
    return json.loads(value) if value else None


async def cache_delete(key: str):
    """Delete cache key"""
    r = await get_redis()
    await r.delete(key)
    await r.close()


# Session Management
async def session_set(session_id: str, data: Dict, ttl: int):
    """Store session data"""
    r = await get_redis()
    await r.setex(f"session:{session_id}", ttl, json.dumps(data))
    await r.close()


async def session_get(session_id: str) -> Optional[Dict]:
    """Get session data"""
    r = await get_redis()
    value = await r.get(f"session:{session_id}")
    await r.close()
    return json.loads(value) if value else None


async def session_delete(session_id: str):
    """Delete session"""
    r = await get_redis()
    await r.delete(f"session:{session_id}")
    await r.close()


# GPS Position Cache
async def set_unit_position(unit_id: str, position: Dict):
    """Cache unit GPS position and publish update"""
    r = await get_redis()
    await r.setex(f"gps:{unit_id}", settings.REDIS_TTL_GPS, json.dumps(position))
    await r.publish("gps.live", json.dumps({"unit_id": unit_id, **position}))
    await r.close()


async def get_all_unit_positions() -> Dict[str, Dict]:
    """Get all cached unit positions"""
    r = await get_redis()
    cursor = 0
    positions = {}

    while True:
        cursor, keys = await r.scan(cursor, match="gps:*", count=100)
        for key in keys:
            value = await r.get(key)
            if value:
                unit_id = key.replace("gps:", "")
                positions[unit_id] = json.loads(value)

        if cursor == 0:
            break

    await r.close()
    return positions


# Threat Cache
async def set_active_threat(threat_id: str, data: Dict):
    """Cache active threat and publish"""
    r = await get_redis()
    await r.setex(f"threat:{threat_id}", settings.REDIS_TTL_THREAT, json.dumps(data))
    await r.publish("threats.live", json.dumps({"threat_id": threat_id, **data}))
    await r.close()


async def get_active_threats() -> List[Dict]:
    """Get all active threats"""
    r = await get_redis()
    cursor = 0
    threats = []

    while True:
        cursor, keys = await r.scan(cursor, match="threat:*", count=100)
        for key in keys:
            value = await r.get(key)
            if value:
                threats.append(json.loads(value))

        if cursor == 0:
            break

    await r.close()
    return threats


# Rate Limiting
async def check_rate_limit(key: str, limit: int, window: int = 60) -> bool:
    """
    Check rate limit using INCR + EXPIRE pattern
    Returns True if under limit, False if exceeded
    """
    r = await get_redis()
    current = await r.incr(key)

    if current == 1:
        await r.expire(key, window)

    await r.close()
    return current <= limit


# PubSub
async def publish_event(channel: str, data: Dict):
    """Publish event to Redis channel"""
    r = await get_redis()
    await r.publish(channel, json.dumps(data))
    await r.close()


async def subscribe_channel(channel: str):
    """Subscribe to Redis channel (generator)"""
    r = await get_redis()
    pubsub = r.pubsub()
    await pubsub.subscribe(channel)

    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                yield json.loads(message["data"])
    finally:
        await pubsub.unsubscribe(channel)
        await r.close()
