from fastapi import FastAPI
from app.api.auth_test import router as auth_test_router
from app.api.routes import customer_lists
from app.api.routes.voice_call import router as voice_call_router
from app.api.routes.plivo_webhook import router as plivo_webhook_router
from app.api.routes.test_tasks import router as test_tasks_router
from app.api.routes.calls import router as calls_router
from app.api.routes.voice_agents import router as voice_agents_router
from app.api.routes.bolna_webhook_test import router
from app.api.routes.phone_numbers import router as phone_numbers_router
from app.api.routes.webhooks import router as webhooks_router
from app.api.routes.customer_lists import router as customer_lists


import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

app = FastAPI(
    title="Voice Calling API",
    version="1.0.0",
)

app.include_router(auth_test_router)
app.include_router(voice_call_router)
app.include_router(plivo_webhook_router)
app.include_router(test_tasks_router)
app.include_router(calls_router)
app.include_router(voice_agents_router)
app.include_router(router)
app.include_router(phone_numbers_router)
app.include_router(webhooks_router)
app.include_router(customer_lists)


@app.get("/health")
async def health_check():
    return {
        "success": True,
        "message": "Voice Calling API is running",
    }
