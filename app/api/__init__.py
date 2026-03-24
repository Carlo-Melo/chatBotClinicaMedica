from fastapi import APIRouter

from app.api.webhook import router as webhook_router


api_router = APIRouter()
api_router.include_router(webhook_router)
