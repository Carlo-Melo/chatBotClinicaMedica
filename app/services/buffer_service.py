import uuid

from redis.asyncio import Redis

from app.config import Settings
from app.models.conversation import NormalizedMessage
from app.utils.errors import ExternalServiceError


class BufferService:
    def __init__(self, redis_client: Redis, settings: Settings) -> None:
        self.redis = redis_client
        self.settings = settings

    def _buffer_key(self, phone: str) -> str:
        return f"conversation:buffer:{phone}"

    def _lock_key(self, phone: str) -> str:
        return f"conversation:lock:{phone}"

    async def enqueue(self, message: NormalizedMessage) -> None:
        key = self._buffer_key(message.phone)
        try:
            async with self.redis.pipeline(transaction=True) as pipeline:
                pipeline.rpush(key, message.model_dump_json())
                pipeline.expire(key, self.settings.message_buffer_ttl_seconds)
                await pipeline.execute()
        except Exception as exc:
            raise ExternalServiceError(
                "Failed to enqueue message into Redis buffer.",
                service="redis",
                details={"reason": str(exc), "phone": message.phone},
            ) from exc

    async def pop_all(self, phone: str) -> list[NormalizedMessage]:
        key = self._buffer_key(phone)
        try:
            async with self.redis.pipeline(transaction=True) as pipeline:
                pipeline.lrange(key, 0, -1)
                pipeline.delete(key)
                items, _ = await pipeline.execute()
        except Exception as exc:
            raise ExternalServiceError(
                "Failed to drain message buffer from Redis.",
                service="redis",
                details={"reason": str(exc), "phone": phone},
            ) from exc

        return [NormalizedMessage.model_validate_json(item) for item in items or []]

    async def has_messages(self, phone: str) -> bool:
        try:
            count = await self.redis.llen(self._buffer_key(phone))
        except Exception as exc:
            raise ExternalServiceError(
                "Failed to inspect pending Redis messages.",
                service="redis",
                details={"reason": str(exc), "phone": phone},
            ) from exc
        return bool(count)

    async def acquire_lock(self, phone: str) -> str | None:
        token = str(uuid.uuid4())
        try:
            acquired = await self.redis.set(
                self._lock_key(phone),
                token,
                ex=self.settings.conversation_lock_ttl_seconds,
                nx=True,
            )
        except Exception as exc:
            raise ExternalServiceError(
                "Failed to acquire Redis lock for conversation.",
                service="redis",
                details={"reason": str(exc), "phone": phone},
            ) from exc

        return token if acquired else None

    async def release_lock(self, phone: str, token: str) -> None:
        key = self._lock_key(phone)
        try:
            current_token = await self.redis.get(key)
            if current_token == token:
                await self.redis.delete(key)
        except Exception as exc:
            raise ExternalServiceError(
                "Failed to release Redis lock for conversation.",
                service="redis",
                details={"reason": str(exc), "phone": phone},
            ) from exc
