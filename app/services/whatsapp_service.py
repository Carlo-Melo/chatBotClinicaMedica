import httpx

from app.config import Settings
from app.utils.errors import ExternalServiceError
from app.utils.helpers import format_chat_id


class WhatsAppService:
    def __init__(self, settings: Settings, http_client: httpx.AsyncClient) -> None:
        self.settings = settings
        self.http_client = http_client

    async def send_text(self, phone: str, text: str) -> dict:
        payload = {
            "chatId": format_chat_id(phone),
            "text": text,
        }
        if self.settings.waha_session:
            payload["session"] = self.settings.waha_session

        headers: dict[str, str] = {}
        if self.settings.waha_api_key:
            headers[self.settings.waha_api_key_header] = self.settings.waha_api_key

        try:
            response = await self.http_client.post(
                self.settings.waha_send_text_path,
                json=payload,
                headers=headers or None,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ExternalServiceError(
                "Failed to send message through WAHA.",
                service="waha",
                details={"reason": str(exc), "phone": phone},
            ) from exc

        if not response.content:
            return {}
        return response.json()
