import asyncio
from datetime import datetime

from loguru import logger

from app.config import Settings
from app.flows.appointment_flow import (
    build_confirmation_prompt,
    build_confirmation_retry_message,
    build_date_prompt,
    build_doctor_prompt,
    build_invalid_date_message,
    build_invalid_doctor_message,
    build_restart_message,
    build_success_message,
)
from app.models.appointment import AppointmentRequest
from app.models.conversation import ConversationContext, ConversationState, FlowDecision
from app.models.patient import Patient
from app.repositories.supabase_client import SupabaseProvider
from app.utils.helpers import is_affirmative, is_negative, parse_appointment_date, strip_accents


class AppointmentService:
    APPOINTMENT_STATES = {
        ConversationState.AGENDAMENTO,
        ConversationState.ESCOLHER_MEDICO,
        ConversationState.ESCOLHER_DATA,
        ConversationState.CONFIRMAR_AGENDAMENTO,
    }

    def __init__(self, settings: Settings, provider: SupabaseProvider) -> None:
        self.settings = settings
        self.provider = provider

    async def handle_message(
        self,
        context: ConversationContext,
        text: str,
        patient: Patient,
    ) -> FlowDecision:
        appointment_data = dict(context.metadata.get("appointment", {}))

        if context.state not in self.APPOINTMENT_STATES:
            return FlowDecision(
                messages=[build_doctor_prompt(self.settings.available_doctors)],
                next_state=ConversationState.ESCOLHER_MEDICO,
                metadata_updates={"appointment": {}},
            )

        if context.state in {ConversationState.AGENDAMENTO, ConversationState.ESCOLHER_MEDICO}:
            doctor = self._resolve_doctor_choice(text)
            if not doctor:
                return FlowDecision(
                    messages=[build_invalid_doctor_message(self.settings.available_doctors)],
                    next_state=ConversationState.ESCOLHER_MEDICO,
                )

            appointment_data["doctor"] = doctor
            return FlowDecision(
                messages=[build_date_prompt(doctor)],
                next_state=ConversationState.ESCOLHER_DATA,
                metadata_updates={"appointment": appointment_data},
            )

        if context.state == ConversationState.ESCOLHER_DATA:
            requested_date, requested_date_iso = parse_appointment_date(
                text,
                self.settings.default_timezone,
            )
            if not requested_date:
                return FlowDecision(
                    messages=[build_invalid_date_message()],
                    next_state=ConversationState.ESCOLHER_DATA,
                )

            appointment_data["requested_date"] = requested_date
            appointment_data["requested_date_iso"] = (
                requested_date_iso.isoformat() if requested_date_iso else None
            )
            return FlowDecision(
                messages=[
                    build_confirmation_prompt(
                        appointment_data.get("doctor", "Clinica"),
                        requested_date,
                    )
                ],
                next_state=ConversationState.CONFIRMAR_AGENDAMENTO,
                metadata_updates={"appointment": appointment_data},
            )

        if is_affirmative(text, self.settings.affirmative_keywords):
            appointment = await self._persist_appointment_request(patient, appointment_data)
            return FlowDecision(
                messages=[
                    build_success_message(
                        appointment.doctor,
                        appointment.requested_date,
                    )
                ],
                next_state=ConversationState.MENU,
                metadata_updates={
                    "appointment": {},
                    "last_appointment_request": appointment.model_dump(mode="json"),
                },
            )

        if is_negative(text, self.settings.negative_keywords):
            return FlowDecision(
                messages=[build_restart_message(), build_doctor_prompt(self.settings.available_doctors)],
                next_state=ConversationState.ESCOLHER_MEDICO,
                metadata_updates={"appointment": {}},
            )

        return FlowDecision(
            messages=[build_confirmation_retry_message()],
            next_state=ConversationState.CONFIRMAR_AGENDAMENTO,
        )

    def _resolve_doctor_choice(self, text: str) -> str | None:
        cleaned = strip_accents(text.lower()).strip()
        if cleaned.isdigit():
            index = int(cleaned) - 1
            if 0 <= index < len(self.settings.available_doctors):
                return self.settings.available_doctors[index]

        for doctor in self.settings.available_doctors:
            normalized_doctor = strip_accents(doctor.lower())
            if normalized_doctor in cleaned or cleaned in normalized_doctor:
                return doctor
        return None

    async def _persist_appointment_request(
        self,
        patient: Patient,
        appointment_data: dict,
    ) -> AppointmentRequest:
        request = AppointmentRequest(
            patient_id=patient.id,
            patient_name=patient.name,
            phone=patient.phone,
            doctor=appointment_data.get("doctor", "Nao informado"),
            requested_date=appointment_data.get("requested_date", "Nao informado"),
            requested_date_iso=self._parse_optional_datetime(appointment_data.get("requested_date_iso")),
            metadata={"source": "whatsapp_bot"},
        )

        try:
            await asyncio.to_thread(
                lambda: self.provider.client.table(self.settings.supabase_appointment_table)
                .insert(request.model_dump(mode="json", exclude_none=True))
                .execute()
            )
        except Exception as exc:
            logger.bind(phone=patient.phone).warning(
                "Failed to persist appointment request in Supabase: {error}",
                error=str(exc),
            )

        return request

    @staticmethod
    def _parse_optional_datetime(value: str | None) -> datetime | None:
        if not value:
            return None
        return datetime.fromisoformat(value)
