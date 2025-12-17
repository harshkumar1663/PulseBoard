"""Redis client configuration."""
import json
from typing import Optional, Any
from redis.asyncio import Redis
from app.core.config import settings


class RedisClient:
    """Async Redis client wrapper."""
    
    def __init__(self):
        self.redis: Optional[Redis] = None
    
    async def connect(self):
        """Initialize Redis connection."""
        self.redis = Redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True
        )
    
    async def disconnect(self):
        """Close Redis connection."""
        if self.redis:
            await self.redis.close()
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from Redis."""
        if not self.redis:
            return None
        value = await self.redis.get(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return None
    
    async def set(
        self,
        key: str,
        value: Any,
        expire: Optional[int] = None
    ) -> bool:
        """Set value in Redis with optional expiration."""
        if not self.redis:
            return False
        
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        
        return await self.redis.set(key, value, ex=expire)
    
    async def delete(self, key: str) -> bool:
        """Delete key from Redis."""
        if not self.redis:
            return False
        return await self.redis.delete(key) > 0
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in Redis."""
        if not self.redis:
            return False
        return await self.redis.exists(key) > 0
    
    async def incr(self, key: str) -> int:
        """Increment value in Redis."""
        if not self.redis:
            return 0
        return await self.redis.incr(key)
    
    async def expire(self, key: str, seconds: int) -> bool:
        """Set expiration on key."""
        if not self.redis:
            return False
        return await self.redis.expire(key, seconds)
    
    async def publish(self, channel: str, message: Any) -> int:
        """Publish message to Redis channel."""
        if not self.redis:
            return 0
        if isinstance(message, (dict, list)):
            message = json.dumps(message)
        return await self.redis.publish(channel, message)


# Global Redis client instance
redis_client = RedisClient()
