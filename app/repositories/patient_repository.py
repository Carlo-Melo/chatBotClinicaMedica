import asyncio

from app.models.patient import Patient
from app.repositories.supabase_client import SupabaseProvider


class PatientRepository:
    def __init__(self, provider: SupabaseProvider, table_name: str) -> None:
        self.provider = provider
        self.table_name = table_name

    async def get_by_phone(self, phone: str) -> Patient | None:
        response = await asyncio.to_thread(
            lambda: self.provider.client.table(self.table_name)
            .select("*")
            .eq("phone", phone)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        if not rows:
            return None
        return Patient.model_validate(rows[0])

    async def create(self, phone: str, name: str | None = None) -> Patient:
        payload = {
            "phone": phone,
            "name": name,
            "metadata": {},
        }
        response = await asyncio.to_thread(
            lambda: self.provider.client.table(self.table_name).insert(payload).execute()
        )
        rows = response.data or []
        return Patient.model_validate(rows[0] if rows else payload)

    async def update_name(self, patient_id: str, name: str) -> None:
        await asyncio.to_thread(
            lambda: self.provider.client.table(self.table_name)
            .update({"name": name})
            .eq("id", patient_id)
            .execute()
        )

    async def get_or_create(self, phone: str, name: str | None = None) -> Patient:
        patient = await self.get_by_phone(phone)
        if patient:
            if name and patient.id and patient.name != name:
                await self.update_name(patient.id, name)
                patient.name = name
            elif name and not patient.name:
                patient.name = name
            return patient
        return await self.create(phone, name)
