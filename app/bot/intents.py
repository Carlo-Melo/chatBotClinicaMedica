from enum import Enum

from app.config import Settings
from app.utils.helpers import strip_accents


class Intent(str, Enum):
    GREETING = "GREETING"
    MENU = "MENU"
    APPOINTMENT = "APPOINTMENT"
    HUMAN_SUPPORT = "HUMAN_SUPPORT"
    RESUME_AI = "RESUME_AI"
    UNKNOWN = "UNKNOWN"


def detect_intent(text: str, settings: Settings) -> Intent:
    normalized = strip_accents(text.lower()).strip()

    if not normalized:
        return Intent.UNKNOWN

    if normalized in {"menu", "inicio", "start", "3"}:
        return Intent.MENU
    if normalized == "1":
        return Intent.APPOINTMENT
    if normalized == "2":
        return Intent.HUMAN_SUPPORT

    if any(keyword in normalized for keyword in settings.resume_ai_keywords):
        return Intent.RESUME_AI
    if any(keyword in normalized for keyword in settings.human_handoff_keywords):
        return Intent.HUMAN_SUPPORT
    if any(keyword in normalized for keyword in settings.appointment_keywords):
        return Intent.APPOINTMENT
    if normalized in {"oi", "ola", "bom dia", "boa tarde", "boa noite"}:
        return Intent.GREETING

    return Intent.UNKNOWN
