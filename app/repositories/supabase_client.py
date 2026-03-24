from supabase import Client, create_client

from app.config import Settings
from app.utils.errors import ExternalServiceError


class SupabaseProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client: Client | None = None

        if settings.supabase_url and settings.supabase_key:
            self._client = create_client(settings.supabase_url, settings.supabase_key)

    @property
    def client(self) -> Client:
        if self._client is None:
            raise ExternalServiceError(
                "Supabase is not configured.",
                service="supabase",
            )
        return self._client
