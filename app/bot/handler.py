import asyncio

from loguru import logger

from app.bot.intents import Intent, detect_intent
from app.bot.state_machine import ConversationStateMachine
from app.config import Settings
from app.flows.support_flow import build_ai_resumed_message, build_human_handoff_message
from app.flows.welcome_flow import build_main_menu
from app.models.conversation import (
    ConversationMessage,
    ConversationState,
    FlowDecision,
    MessageType,
    NormalizedMessage,
    SenderRole,
)
from app.models.patient import Patient
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.patient_repository import PatientRepository
from app.services.ai_service import GeminiAIService
from app.services.appointment_service import AppointmentService
from app.services.buffer_service import BufferService
from app.services.whatsapp_service import WhatsAppService
from app.utils.errors import ExternalServiceError
from app.utils.helpers import normalize_waha_payload, split_text, utcnow


class BotHandler:
    def __init__(
        self,
        *,
        settings: Settings,
        patient_repository: PatientRepository,
        conversation_repository: ConversationRepository,
        state_machine: ConversationStateMachine,
        buffer_service: BufferService,
        whatsapp_service: WhatsAppService,
        ai_service: GeminiAIService,
        appointment_service: AppointmentService,
    ) -> None:
        self.settings = settings
        self.patient_repository = patient_repository
        self.conversation_repository = conversation_repository
        self.state_machine = state_machine
        self.buffer_service = buffer_service
        self.whatsapp_service = whatsapp_service
        self.ai_service = ai_service
        self.appointment_service = appointment_service
        self._tasks: set[asyncio.Task] = set()
        self._local_locks: dict[str, asyncio.Lock] = {}

    async def handle_incoming_payload(self, payload: dict) -> dict:
        message = normalize_waha_payload(payload)
        logger.bind(phone=message.phone, message_type=message.message_type.value).info("Webhook received")

        if message.from_me:
            return {"status": "ignored", "reason": "from_me"}

        patient = await self._safe_get_or_create_patient(message)
        await self._safe_save_history(
            ConversationMessage(
                phone=message.phone,
                message=self._history_text_for_message(message),
                sender=SenderRole.USER,
                timestamp=message.timestamp,
                message_type=message.message_type,
                metadata={"message_id": message.message_id},
            )
        )

        try:
            await self.buffer_service.enqueue(message)
            self._schedule_task(self.process_buffered_messages(message.phone))
            processing_mode = "buffered"
        except ExternalServiceError as exc:
            logger.bind(phone=message.phone).warning(
                "Redis buffer unavailable. Falling back to direct processing: {error}",
                error=exc.message,
            )
            self._schedule_task(self.process_message_directly(message))
            processing_mode = "direct"

        return {
            "status": "accepted",
            "phone": patient.phone,
            "processing_mode": processing_mode,
        }

    async def process_buffered_messages(self, phone: str) -> None:
        try:
            token = await self.buffer_service.acquire_lock(phone)
        except ExternalServiceError as exc:
            logger.bind(phone=phone).warning(
                "Could not acquire Redis lock. Processing skipped: {error}",
                error=exc.message,
            )
            return

        if not token:
            return

        try:
            while True:
                await asyncio.sleep(self.settings.message_buffer_seconds)
                batch = await self.buffer_service.pop_all(phone)
                if not batch:
                    break

                await self._process_batch(phone, batch)

                if not await self.buffer_service.has_messages(phone):
                    break
        except ExternalServiceError as exc:
            logger.bind(phone=phone).warning(
                "Buffered processing failed: {error}",
                error=exc.message,
            )
        except Exception as exc:
            logger.bind(phone=phone).exception(
                "Unexpected error while processing buffered messages: {error}",
                error=str(exc),
            )
        finally:
            await self._safe_release_lock(phone, token)

    async def process_message_directly(self, message: NormalizedMessage) -> None:
        lock = self._local_locks.setdefault(message.phone, asyncio.Lock())
        async with lock:
            try:
                await self._process_batch(message.phone, [message])
            except Exception as exc:
                logger.bind(phone=message.phone).exception(
                    "Unexpected error while processing direct message: {error}",
                    error=str(exc),
                )

    async def shutdown(self) -> None:
        pending = [task for task in self._tasks if not task.done()]
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

    def _schedule_task(self, coroutine) -> None:
        task = asyncio.create_task(coroutine)
        self._tasks.add(task)
        task.add_done_callback(lambda done_task: self._tasks.discard(done_task))

    async def _process_batch(self, phone: str, batch: list[NormalizedMessage]) -> None:
        context = await self.state_machine.get_context(phone)
        patient = await self._safe_get_patient(phone, fallback_name=batch[-1].name if batch else None)
        consolidated_text = await self._consolidate_messages(batch)
        intent = detect_intent(consolidated_text, self.settings)

        logger.bind(
            phone=phone,
            state=context.state.value,
            batch_size=len(batch),
            intent=intent.value,
        ).info("Processing message batch")

        if context.state == ConversationState.IA_PAUSADA:
            if intent == Intent.RESUME_AI:
                await self.state_machine.resume_ai(phone)
                await self._send_messages(phone, [build_ai_resumed_message()])
            else:
                logger.bind(phone=phone).info("AI paused. No automatic response sent.")
            return

        if intent == Intent.MENU:
            await self._apply_flow_decision(
                phone,
                FlowDecision(
                    messages=[build_main_menu(patient.name)],
                    next_state=ConversationState.MENU,
                    ai_paused=False,
                    metadata_updates={"appointment": {}},
                ),
            )
            return

        if intent == Intent.HUMAN_SUPPORT:
            await self.state_machine.update_context(phone, state=ConversationState.SUPORTE_HUMANO)
            await self.state_machine.pause_ai(
                phone,
                previous_state=ConversationState.SUPORTE_HUMANO,
            )
            await self._send_messages(phone, [build_human_handoff_message()])
            return

        if intent in {Intent.GREETING, Intent.MENU} and context.state in {
            ConversationState.START,
            ConversationState.MENU,
        }:
            await self._apply_flow_decision(
                phone,
                FlowDecision(
                    messages=[build_main_menu(patient.name)],
                    next_state=ConversationState.MENU,
                ),
            )
            return

        if context.state in AppointmentService.APPOINTMENT_STATES or intent == Intent.APPOINTMENT:
            decision = await self.appointment_service.handle_message(context, consolidated_text, patient)
            await self._apply_flow_decision(phone, decision)
            return

        history = await self._safe_load_history(phone)
        try:
            reply = await self.ai_service.generate_reply(
                patient=patient,
                context=context,
                consolidated_message=consolidated_text,
                history=history,
            )
        except ExternalServiceError as exc:
            logger.bind(phone=phone).warning(
                "AI response failed. Sending fallback message: {error}",
                error=exc.message,
            )
            reply = (
                "No momento estou com uma instabilidade no atendimento automatico. "
                "Se preferir, posso te encaminhar para nossa equipe humana."
            )

        await self._send_messages(phone, [reply])
        if context.state == ConversationState.START:
            await self.state_machine.update_context(phone, state=ConversationState.MENU)

    async def _apply_flow_decision(self, phone: str, decision: FlowDecision) -> None:
        if decision.next_state is not None or decision.ai_paused is not None or decision.metadata_updates:
            await self.state_machine.update_context(
                phone,
                state=decision.next_state,
                ai_paused=decision.ai_paused,
                metadata_updates=decision.metadata_updates,
            )

        if decision.messages:
            await self._send_messages(phone, decision.messages)

    async def _consolidate_messages(self, batch: list[NormalizedMessage]) -> str:
        parts: list[str] = []
        for message in batch:
            if message.text:
                parts.append(message.text)

            if message.message_type == MessageType.AUDIO and message.media_url:
                try:
                    transcript = await self.ai_service.transcribe_audio(message.media_url, message.mime_type)
                    parts.append(f"Audio transcrito: {transcript}")
                except ExternalServiceError:
                    parts.append("O usuario enviou um audio.")
            elif message.message_type == MessageType.IMAGE and message.media_url:
                try:
                    analysis = await self.ai_service.analyze_image(message.media_url, message.mime_type)
                    parts.append(f"Imagem enviada: {analysis}")
                except ExternalServiceError:
                    parts.append("O usuario enviou uma imagem.")
            elif message.message_type == MessageType.STICKER:
                parts.append("O usuario enviou um sticker.")

        consolidated = "\n".join(part for part in parts if part).strip()
        return consolidated or "Mensagem recebida sem texto."

    async def _send_messages(self, phone: str, messages: list[str]) -> None:
        for message in messages:
            for chunk in split_text(message, self.settings.max_outbound_message_length):
                try:
                    await self.whatsapp_service.send_text(phone, chunk)
                    logger.bind(phone=phone).info("Response sent to WAHA")
                except ExternalServiceError as exc:
                    logger.bind(phone=phone).warning(
                        "Failed to send outbound message: {error}",
                        error=exc.message,
                    )
                    continue

                await self._safe_save_history(
                    ConversationMessage(
                        phone=phone,
                        message=chunk,
                        sender=SenderRole.BOT,
                        timestamp=utcnow(),
                        message_type=MessageType.TEXT,
                    )
                )

    async def _safe_get_or_create_patient(self, message: NormalizedMessage) -> Patient:
        try:
            return await self.patient_repository.get_or_create(message.phone, message.name)
        except Exception as exc:
            logger.bind(phone=message.phone).warning(
                "Patient lookup failed. Continuing with transient patient object: {error}",
                error=str(exc),
            )
            return Patient(phone=message.phone, name=message.name)

    async def _safe_get_patient(self, phone: str, fallback_name: str | None = None) -> Patient:
        try:
            patient = await self.patient_repository.get_by_phone(phone)
            if patient:
                return patient
        except Exception as exc:
            logger.bind(phone=phone).warning(
                "Patient recovery failed. Continuing without persistent profile: {error}",
                error=str(exc),
            )
        return Patient(phone=phone, name=fallback_name)

    async def _safe_save_history(self, message: ConversationMessage) -> None:
        try:
            await self.conversation_repository.save_message(message)
        except Exception as exc:
            logger.bind(phone=message.phone).warning(
                "Failed to save conversation history: {error}",
                error=str(exc),
            )

    async def _safe_load_history(self, phone: str) -> list[ConversationMessage]:
        try:
            return await self.conversation_repository.get_recent_history(phone, self.settings.history_limit)
        except Exception as exc:
            logger.bind(phone=phone).warning(
                "Failed to load recent history: {error}",
                error=str(exc),
            )
            return []

    async def _safe_release_lock(self, phone: str, token: str) -> None:
        try:
            await self.buffer_service.release_lock(phone, token)
        except ExternalServiceError as exc:
            logger.bind(phone=phone).warning(
                "Failed to release Redis lock: {error}",
                error=exc.message,
            )

    @staticmethod
    def _history_text_for_message(message: NormalizedMessage) -> str:
        if message.text:
            return message.text
        if message.message_type == MessageType.AUDIO:
            return "[audio]"
        if message.message_type == MessageType.IMAGE:
            return "[image]"
        if message.message_type == MessageType.STICKER:
            return "[sticker]"
        return "[message]"
