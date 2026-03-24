from functools import lru_cache
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "clinic-whatsapp-bot"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    redis_url: str = "redis://localhost:6379/0"
    redis_state_ttl_seconds: int = 2_592_000
    message_buffer_seconds: float = 3.0
    message_buffer_ttl_seconds: int = 300
    conversation_lock_ttl_seconds: int = 120

    history_limit: int = 20
    max_outbound_message_length: int = 850
    default_timezone: str = "America/Sao_Paulo"

    supabase_url: str | None = None
    supabase_key: str | None = None
    supabase_patient_table: str = "patients"
    supabase_conversation_table: str = "conversation_history"
    supabase_appointment_table: str = "appointment_requests"

    waha_base_url: str = "http://localhost:3000"
    waha_send_text_path: str = "/api/sendText"
    waha_api_key: str | None = None
    waha_api_key_header: str = "X-Api-Key"
    waha_session: str | None = "default"
    waha_request_timeout_seconds: float = 15.0

    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    gemini_request_timeout_seconds: float = 40.0
    gemini_temperature: float = 0.7

    system_prompt: str = (
        "Voce e a assistente virtual de uma clinica medica no WhatsApp. "
        "Seja educada, objetiva e clara. "
        "Ajude com agendamentos, duvidas gerais e orientacoes iniciais. "
        "Quando nao souber algo, diga que a equipe humana vai confirmar. "
        "Evite respostas longas demais e use portugues do Brasil."
    )

    available_doctors: list[str] = Field(
        default_factory=lambda: [
            "Clinico Geral",
            "Cardiologia",
            "Dermatologia",
        ]
    )
    appointment_keywords: list[str] = Field(
        default_factory=lambda: [
            "agendar",
            "agendamento",
            "consulta",
            "marcar",
            "horario",
        ]
    )
    human_handoff_keywords: list[str] = Field(
        default_factory=lambda: [
            "atendente",
            "humano",
            "pessoa",
            "suporte",
            "secretaria",
        ]
    )
    resume_ai_keywords: list[str] = Field(
        default_factory=lambda: [
            "voltar para o bot",
            "reativar ia",
            "retomar atendimento",
            "voltar ao atendimento automatico",
        ]
    )
    affirmative_keywords: list[str] = Field(
        default_factory=lambda: [
            "sim",
            "confirmo",
            "pode confirmar",
            "ok",
            "certo",
        ]
    )
    negative_keywords: list[str] = Field(
        default_factory=lambda: [
            "nao",
            "cancelar",
            "corrigir",
            "voltar",
        ]
    )

    @field_validator(
        "available_doctors",
        "appointment_keywords",
        "human_handoff_keywords",
        "resume_ai_keywords",
        "affirmative_keywords",
        "negative_keywords",
        mode="before",
    )
    @classmethod
    def split_csv_values(cls, value: Any) -> Any:
        if value is None:
            return value
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
