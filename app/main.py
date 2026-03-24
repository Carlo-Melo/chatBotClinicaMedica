from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from redis.asyncio import Redis

from app.api import api_router
from app.bot.handler import BotHandler
from app.bot.state_machine import ConversationStateMachine
from app.config import get_settings
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.patient_repository import PatientRepository
from app.repositories.supabase_client import SupabaseProvider
from app.services.ai_service import GeminiAIService
from app.services.appointment_service import AppointmentService
from app.services.buffer_service import BufferService
from app.services.whatsapp_service import WhatsAppService
from app.utils.errors import register_exception_handlers
from app.utils.logger import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings)

    redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
    waha_http_client = httpx.AsyncClient(
        base_url=settings.waha_base_url.rstrip("/"),
        timeout=settings.waha_request_timeout_seconds,
    )
    gemini_http_client = httpx.AsyncClient(timeout=settings.gemini_request_timeout_seconds)

    supabase_provider = SupabaseProvider(settings)
    patient_repository = PatientRepository(supabase_provider, settings.supabase_patient_table)
    conversation_repository = ConversationRepository(
        supabase_provider,
        settings.supabase_conversation_table,
    )
    state_machine = ConversationStateMachine(redis_client, settings)
    buffer_service = BufferService(redis_client, settings)
    whatsapp_service = WhatsAppService(settings, waha_http_client)
    ai_service = GeminiAIService(settings, gemini_http_client)
    appointment_service = AppointmentService(settings, supabase_provider)

    app.state.bot_handler = BotHandler(
        settings=settings,
        patient_repository=patient_repository,
        conversation_repository=conversation_repository,
        state_machine=state_machine,
        buffer_service=buffer_service,
        whatsapp_service=whatsapp_service,
        ai_service=ai_service,
        appointment_service=appointment_service,
    )

    yield

    await app.state.bot_handler.shutdown()
    await waha_http_client.aclose()
    await gemini_http_client.aclose()
    await redis_client.aclose()


app = FastAPI(title="Clinic WhatsApp Bot", lifespan=lifespan)
register_exception_handlers(app)
app.include_router(api_router)
