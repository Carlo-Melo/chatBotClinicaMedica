from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MessageType(str, Enum):
    TEXT = "text"
    AUDIO = "audio"
    IMAGE = "image"
    STICKER = "sticker"
    UNKNOWN = "unknown"


class SenderRole(str, Enum):
    USER = "user"
    BOT = "bot"
    HUMAN = "human"
    SYSTEM = "system"


class ConversationState(str, Enum):
    START = "START"
    MENU = "MENU"
    AGENDAMENTO = "AGENDAMENTO"
    ESCOLHER_MEDICO = "ESCOLHER_MEDICO"
    ESCOLHER_DATA = "ESCOLHER_DATA"
    CONFIRMAR_AGENDAMENTO = "CONFIRMAR_AGENDAMENTO"
    SUPORTE_HUMANO = "SUPORTE_HUMANO"
    IA_PAUSADA = "IA_PAUSADA"


class NormalizedMessage(BaseModel):
    model_config = ConfigDict(extra="allow")

    phone: str
    text: str = ""
    message_type: MessageType = MessageType.TEXT
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    name: str | None = None
    media_url: str | None = None
    mime_type: str | None = None
    message_id: str | None = None
    from_me: bool = False
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class ConversationMessage(BaseModel):
    phone: str
    message: str
    sender: SenderRole
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    message_type: MessageType = MessageType.TEXT
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConversationContext(BaseModel):
    phone: str
    state: ConversationState = ConversationState.START
    ai_paused: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class FlowDecision(BaseModel):
    messages: list[str] = Field(default_factory=list)
    next_state: ConversationState | None = None
    ai_paused: bool | None = None
    metadata_updates: dict[str, Any] = Field(default_factory=dict)
