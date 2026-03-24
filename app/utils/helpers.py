import re
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from app.models.conversation import MessageType, NormalizedMessage
from app.utils.errors import ValidationAppError


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(character for character in normalized if not unicodedata.combining(character))


def normalize_phone(raw_phone: str | int | None) -> str:
    if raw_phone is None:
        raise ValidationAppError("Webhook payload is missing the sender phone number.")

    digits = "".join(character for character in str(raw_phone) if character.isdigit())
    if not digits:
        raise ValidationAppError("Could not extract a valid phone number from webhook payload.")
    return digits


def format_chat_id(phone: str) -> str:
    clean_phone = normalize_phone(phone)
    return clean_phone if clean_phone.endswith("@c.us") else f"{clean_phone}@c.us"


def compact_whitespace(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def parse_timestamp(value: Any) -> datetime:
    if value is None:
        return utcnow()

    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

    if isinstance(value, (int, float)):
        if value > 10_000_000_000:
            value = value / 1000
        return datetime.fromtimestamp(value, tz=timezone.utc)

    if isinstance(value, str):
        try:
            if value.endswith("Z"):
                value = value.replace("Z", "+00:00")
            parsed = datetime.fromisoformat(value)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            return utcnow()

    return utcnow()


def split_text(text: str, max_length: int) -> list[str]:
    if len(text) <= max_length:
        return [text]

    chunks: list[str] = []
    current = ""

    for word in text.split():
        if len(word) > max_length:
            if current:
                chunks.append(current)
                current = ""
            for index in range(0, len(word), max_length):
                chunks.append(word[index : index + max_length])
            continue

        candidate = word if not current else f"{current} {word}"
        if len(candidate) <= max_length:
            current = candidate
            continue

        if current:
            chunks.append(current)
        current = word

    if current:
        chunks.append(current)

    return chunks


def _get_nested(payload: dict[str, Any], *path: str) -> Any:
    current: Any = payload
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def normalize_message_type(raw_type: str | None) -> MessageType:
    if not raw_type:
        return MessageType.TEXT

    normalized = raw_type.lower()
    if normalized in {"text", "chat", "textmessage"}:
        return MessageType.TEXT
    if "audio" in normalized or normalized in {"ptt", "voice"}:
        return MessageType.AUDIO
    if "image" in normalized or "photo" in normalized:
        return MessageType.IMAGE
    if "sticker" in normalized:
        return MessageType.STICKER
    return MessageType.UNKNOWN


def normalize_waha_payload(payload: dict[str, Any]) -> NormalizedMessage:
    phone = normalize_phone(
        payload.get("from")
        or payload.get("chatId")
        or payload.get("author")
        or _get_nested(payload, "chat", "id")
    )

    raw_text = payload.get("body")
    if raw_text is None:
        raw_text = payload.get("text")
    if isinstance(raw_text, dict):
        raw_text = raw_text.get("body") or raw_text.get("text")
    if raw_text is None:
        raw_text = _get_nested(payload, "message", "text")
    if raw_text is None:
        raw_text = _get_nested(payload, "text", "body")

    raw_type = payload.get("type") or payload.get("messageType")
    media_url = (
        payload.get("mediaUrl")
        or _get_nested(payload, "media", "url")
        or _get_nested(payload, "file", "url")
        or _get_nested(payload, "image", "url")
        or _get_nested(payload, "audio", "url")
    )
    mime_type = (
        payload.get("mimeType")
        or _get_nested(payload, "media", "mimeType")
        or _get_nested(payload, "file", "mimeType")
    )
    message_id = payload.get("id") or payload.get("messageId")
    if isinstance(message_id, dict):
        message_id = message_id.get("_serialized") or message_id.get("id")

    name = (
        payload.get("name")
        or payload.get("pushName")
        or _get_nested(payload, "sender", "name")
        or _get_nested(payload, "contact", "name")
    )

    return NormalizedMessage(
        phone=phone,
        text=compact_whitespace(str(raw_text or "")),
        message_type=normalize_message_type(str(raw_type or "text")),
        timestamp=parse_timestamp(payload.get("timestamp") or payload.get("time")),
        name=compact_whitespace(str(name)) if name else None,
        media_url=media_url,
        mime_type=mime_type,
        message_id=str(message_id) if message_id else None,
        from_me=bool(payload.get("fromMe") or payload.get("from_me")),
        raw_payload=payload,
    )


def parse_appointment_date(
    text: str,
    timezone_name: str,
) -> tuple[str | None, datetime | None]:
    cleaned = strip_accents(text.lower()).strip()
    now = datetime.now(ZoneInfo(timezone_name))

    if "hoje" in cleaned:
        target = now
        return target.strftime("%d/%m/%Y"), target

    if "amanha" in cleaned:
        target = now + timedelta(days=1)
        return target.strftime("%d/%m/%Y"), target

    weekdays = {
        "segunda": 0,
        "terca": 1,
        "quarta": 2,
        "quinta": 3,
        "sexta": 4,
        "sabado": 5,
        "domingo": 6,
    }
    for label, weekday in weekdays.items():
        if label in cleaned:
            delta = (weekday - now.weekday()) % 7
            delta = 7 if delta == 0 else delta
            target = now + timedelta(days=delta)
            return target.strftime("%d/%m/%Y"), target

    for date_format in ("%d/%m/%Y", "%d/%m"):
        try:
            parsed = datetime.strptime(cleaned, date_format)
            if date_format == "%d/%m":
                parsed = parsed.replace(year=now.year)
                if parsed.date() < now.date():
                    parsed = parsed.replace(year=now.year + 1)
            parsed = parsed.replace(tzinfo=ZoneInfo(timezone_name))
            return parsed.strftime("%d/%m/%Y"), parsed
        except ValueError:
            continue

    return None, None


def is_affirmative(text: str, keywords: list[str]) -> bool:
    normalized = strip_accents(text.lower())
    return any(keyword in normalized for keyword in keywords)


def is_negative(text: str, keywords: list[str]) -> bool:
    normalized = strip_accents(text.lower())
    return any(keyword in normalized for keyword in keywords)
