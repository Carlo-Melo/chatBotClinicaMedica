import base64

import httpx

from app.config import Settings
from app.models.conversation import ConversationContext, ConversationMessage
from app.models.patient import Patient
from app.utils.errors import ExternalServiceError


class GeminiAIService:
    def __init__(self, settings: Settings, http_client: httpx.AsyncClient) -> None:
        self.settings = settings
        self.http_client = http_client

    async def generate_reply(
        self,
        *,
        patient: Patient,
        context: ConversationContext,
        consolidated_message: str,
        history: list[ConversationMessage],
    ) -> str:
        history_text = "\n".join(
            f"{item.sender.value.upper()}: {item.message}" for item in history[-self.settings.history_limit :]
        )
        payload = {
            "system_instruction": {
                "parts": [{"text": self.settings.system_prompt}],
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": (
                                f"Paciente: {patient.name or 'Nao identificado'}\n"
                                f"Telefone: {patient.phone}\n"
                                f"Estado atual: {context.state.value}\n"
                                f"Historico recente:\n{history_text or 'Sem historico registrado.'}\n\n"
                                "Responda de forma curta, clara e pronta para WhatsApp.\n\n"
                                f"Ultima mensagem consolidada do paciente:\n{consolidated_message}"
                            )
                        }
                    ],
                }
            ],
            "generationConfig": {
                "temperature": self.settings.gemini_temperature,
                "maxOutputTokens": 512,
            },
        }
        response = await self._generate_content(payload)
        return self._extract_text(response)

    async def transcribe_audio(self, media_url: str, mime_type: str | None = None) -> str:
        media_part = await self._build_inline_media_part(media_url, mime_type)
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": "Transcreva este audio. Responda apenas com a transcricao."},
                        media_part,
                    ],
                }
            ]
        }
        response = await self._generate_content(payload)
        return self._extract_text(response)

    async def analyze_image(self, media_url: str, mime_type: str | None = None) -> str:
        media_part = await self._build_inline_media_part(media_url, mime_type)
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": (
                                "Descreva a imagem para um atendimento de clinica medica. "
                                "Se houver documento, exame ou pedido, resuma os pontos principais."
                            )
                        },
                        media_part,
                    ],
                }
            ]
        }
        response = await self._generate_content(payload)
        return self._extract_text(response)

    async def _build_inline_media_part(self, media_url: str, mime_type: str | None = None) -> dict:
        try:
            response = await self.http_client.get(media_url)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ExternalServiceError(
                "Failed to download media before sending it to Gemini.",
                service="gemini",
                details={"reason": str(exc), "media_url": media_url},
            ) from exc

        detected_mime = mime_type or response.headers.get("content-type") or "application/octet-stream"
        encoded = base64.b64encode(response.content).decode("utf-8")
        return {
            "inlineData": {
                "mimeType": detected_mime,
                "data": encoded,
            }
        }

    async def _generate_content(self, payload: dict) -> dict:
        if not self.settings.gemini_api_key:
            raise ExternalServiceError(
                "Gemini API key is not configured.",
                service="gemini",
            )

        model_name = (
            self.settings.gemini_model
            if self.settings.gemini_model.startswith("models/")
            else f"models/{self.settings.gemini_model}"
        )
        url = f"{self.settings.gemini_base_url.rstrip('/')}/{model_name}:generateContent"

        try:
            response = await self.http_client.post(
                url,
                json=payload,
                headers={"x-goog-api-key": self.settings.gemini_api_key},
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ExternalServiceError(
                "Gemini request failed.",
                service="gemini",
                details={"reason": str(exc)},
            ) from exc

        return response.json()

    @staticmethod
    def _extract_text(payload: dict) -> str:
        candidates = payload.get("candidates") or []
        if not candidates:
            raise ExternalServiceError(
                "Gemini returned no candidates.",
                service="gemini",
            )

        parts = candidates[0].get("content", {}).get("parts", [])
        text_parts = [part.get("text", "").strip() for part in parts if part.get("text")]
        message = "\n".join(part for part in text_parts if part).strip()

        if not message:
            raise ExternalServiceError(
                "Gemini returned an empty response.",
                service="gemini",
            )
        return message
