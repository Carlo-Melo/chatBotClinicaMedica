from redis.asyncio import Redis

from app.config import Settings
from app.models.conversation import ConversationContext, ConversationState
from app.utils.helpers import utcnow
from app.utils.logger import get_logger


class ConversationStateMachine:
    def __init__(self, redis_client: Redis, settings: Settings) -> None:
        self.redis = redis_client
        self.settings = settings

    def _state_key(self, phone: str) -> str:
        return f"conversation:state:{phone}"

    async def get_context(self, phone: str) -> ConversationContext:
        try:
            raw_context = await self.redis.get(self._state_key(phone))
            if not raw_context:
                return ConversationContext(phone=phone)
            return ConversationContext.model_validate_json(raw_context)
        except Exception as exc:
            get_logger(phone=phone).warning(
                "Failed to load conversation state from Redis: {error}",
                error=str(exc),
            )
            return ConversationContext(phone=phone)

    async def save_context(self, context: ConversationContext) -> ConversationContext:
        context.updated_at = utcnow()
        try:
            await self.redis.set(
                self._state_key(context.phone),
                context.model_dump_json(),
                ex=self.settings.redis_state_ttl_seconds,
            )
        except Exception as exc:
            get_logger(phone=context.phone).warning(
                "Failed to persist conversation state in Redis: {error}",
                error=str(exc),
            )
        return context

    async def update_context(
        self,
        phone: str,
        *,
        state: ConversationState | None = None,
        ai_paused: bool | None = None,
        metadata_updates: dict | None = None,
    ) -> ConversationContext:
        context = await self.get_context(phone)
        if state is not None:
            context.state = state
        if ai_paused is not None:
            context.ai_paused = ai_paused
        if metadata_updates:
            context.metadata = self._merge_dicts(context.metadata, metadata_updates)
        return await self.save_context(context)

    async def pause_ai(
        self,
        phone: str,
        *,
        previous_state: ConversationState | None = None,
    ) -> ConversationContext:
        metadata_updates = {
            "handoff": {
                "requested_at": utcnow().isoformat(),
                "previous_state": previous_state.value if previous_state else None,
            }
        }
        return await self.update_context(
            phone,
            state=ConversationState.IA_PAUSADA,
            ai_paused=True,
            metadata_updates=metadata_updates,
        )

    async def resume_ai(self, phone: str) -> ConversationContext:
        return await self.update_context(
            phone,
            state=ConversationState.MENU,
            ai_paused=False,
            metadata_updates={"handoff": {"resumed_at": utcnow().isoformat()}},
        )

    @classmethod
    def _merge_dicts(cls, current: dict, updates: dict) -> dict:
        merged = dict(current)
        for key, value in updates.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = cls._merge_dicts(merged[key], value)
            else:
                merged[key] = value
        return merged
