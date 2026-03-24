from typing import Any

from fastapi import APIRouter, Request

from app.bot.handler import BotHandler


router = APIRouter()


def get_bot_handler(request: Request) -> BotHandler:
    return request.app.state.bot_handler


@router.get("/health")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/webhook")
async def receive_webhook(payload: dict[str, Any], request: Request) -> dict[str, Any]:
    handler = get_bot_handler(request)
    return await handler.handle_incoming_payload(payload)
