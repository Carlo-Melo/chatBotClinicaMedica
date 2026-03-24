import asyncio

from app.models.conversation import ConversationMessage
from app.repositories.supabase_client import SupabaseProvider


class ConversationRepository:
    def __init__(self, provider: SupabaseProvider, table_name: str) -> None:
        self.provider = provider
        self.table_name = table_name

    async def save_message(self, message: ConversationMessage) -> None:
        payload = message.model_dump(mode="json")
        await asyncio.to_thread(
            lambda: self.provider.client.table(self.table_name).insert(payload).execute()
        )

    async def get_recent_history(self, phone: str, limit: int) -> list[ConversationMessage]:
        response = await asyncio.to_thread(
            lambda: self.provider.client.table(self.table_name)
            .select("*")
            .eq("phone", phone)
            .order("timestamp", desc=True)
            .limit(limit)
            .execute()
        )
        rows = response.data or []
        return [ConversationMessage.model_validate(row) for row in reversed(rows)]
