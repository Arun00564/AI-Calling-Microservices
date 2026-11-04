import json
import hmac

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models.user_details import UserDetails
from app.db.models.provider_webhook import ProviderWebhook
from app.api.dependencies import get_current_user
from app.core.encryption import encrypt_value
from app.schemas.webhook import VoizematicWebhookRegisterRequest
from app.services.voizematic import VoizematicWebhookService

from app.core.encryption import decrypt_value

import logging

# logger = logging.getLogger(__name__)
logger = logging.getLogger("voizematic_webhook")

router = APIRouter(
    prefix="/api/v1/webhooks",
    tags=["Webhooks"],
)


@router.post("/voizematic/register/")
async def register_voizematic_webhook(
    request: VoizematicWebhookRegisterRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserDetails = Depends(get_current_user),
):
    provider = "voizematic"
    account_key = "default"

    # Check existing registration
    result = await db.execute(
        select(ProviderWebhook).where(
            ProviderWebhook.provider == provider,
            ProviderWebhook.provider_account_key == account_key,
            ProviderWebhook.is_active.is_(True),
        )
    )

    existing_webhook = result.scalar_one_or_none()

    if existing_webhook:
        return {
            "success": True,
            "message": "Webhook is already registered.",
            "data": {
                "webhook_id": existing_webhook.webhook_id,
                "webhook_url": existing_webhook.webhook_url,
                "events": existing_webhook.events,
                "is_active": existing_webhook.is_active,
            },
        }

    # Register webhook with Voizematic
    payload = {
        "url": str(request.url),
        "events": request.events,
    }

    service = VoizematicWebhookService()

    provider_response = await service.register_webhook(payload=payload)

    # Extract provider response
    webhook_id = provider_response.get("id")
    webhook_url = provider_response.get("url")
    events = provider_response.get("events", [])
    secret = provider_response.get("secret")

    if not webhook_id or not webhook_url or not secret:
        raise Exception("Invalid webhook registration response from Voizematic.")

    # Save webhook details
    webhook = ProviderWebhook(
        provider=provider,
        provider_account_key=account_key,
        webhook_id=webhook_id,
        webhook_url=webhook_url,
        events=events,
        webhook_secret_encrypted=encrypt_value(secret),
        is_active=True,
    )

    db.add(webhook)
    await db.commit()
    await db.refresh(webhook)

    return {
        "status": status.HTTP_201_CREATED,
        "success": True,
        "message": "Webhook registered successfully.",
        "data": {
            "id": webhook.id,
            "webhook_id": webhook.webhook_id,
            "webhook_url": webhook.webhook_url,
            "events": webhook.events,
            "is_active": webhook.is_active,
        },
    }


# @router.post("/voizematic")
# async def receive_voizematic_webhook(
#     request: Request,
#     db: AsyncSession = Depends(get_db),
# ):
#     # 1. Read raw request body
#     raw_body = await request.body()
#     print("\n========== VOIZEMATIC WEBHOOK ==========")
#     print("Raw request body:----", raw_body.decode("utf-8", errors="replace"))

#     try:
#         payload = json.loads(raw_body) if raw_body else {}
#     except json.JSONDecodeError:
#         payload = {"raw_body": raw_body.decode("utf-8", errors="replace")}

#     print("Payload:-----", payload)

#     # 2. Read Voizematic headers
#     signature = request.headers.get("X-Voizematic-Signature")
#     event_header = request.headers.get("X-Voizematic-Event")

#     logger.info("Voizematic webhook received")
#     logger.info("Webhook event header: %s", event_header)
#     logger.info("Webhook body: %s", raw_body.decode("utf-8", errors="replace"))
#     logger.info("Signature header received: %s", bool(signature))

#     if not signature or not event_header:
#         raise HTTPException(
#             status_code=401,
#             detail="Missing webhook signature or event header.",
#         )

#     # 3. Get active webhook registration
#     result = await db.execute(
#         select(ProviderWebhook).where(
#             ProviderWebhook.provider == "voizematic",
#             ProviderWebhook.provider_account_key == "default",
#             ProviderWebhook.is_active.is_(True),
#         )
#     )

#     webhook = result.scalar_one_or_none()

#     if not webhook or not webhook.webhook_secret_encrypted:
#         raise HTTPException(
#             status_code=401,
#             detail="Webhook registration not found.",
#         )

#     # 4. Decrypt webhook secret
#     secret = decrypt_value(webhook.webhook_secret_encrypted)

#     # 5. Verify HMAC-SHA256 signature
#     expected_signature = hmac.new(
#         secret.encode("utf-8"),
#         raw_body,
#         digestmod="sha256",
#     ).hexdigest()

#     received_signature = signature.strip()

#     # Support an optional sha256= prefix.
#     if received_signature.startswith("sha256="):
#         received_signature = received_signature[7:]

#     if not hmac.compare_digest(
#         expected_signature,
#         received_signature,
#     ):
#         raise HTTPException(
#             status_code=401,
#             detail="Invalid webhook signature.",
#         )

#     # 6. Parse JSON only after signature verification
#     try:
#         payload = json.loads(raw_body)
#     except json.JSONDecodeError:
#         raise HTTPException(
#             status_code=400,
#             detail="Invalid webhook JSON payload.",
#         )

#     # 7. Validate event name
#     body_event = payload.get("event")

#     if body_event and body_event != event_header:
#         raise HTTPException(
#             status_code=400,
#             detail="Webhook event header does not match payload.",
#         )

#     # if event_header not in webhook.events:
#     #     raise HTTPException(
#     #         status_code=400,
#     #         detail="Unsupported webhook event.",
#     #     )

#     # Allow provider test events after signature verification.
#     if event_header != "webhook.test" and event_header not in webhook.events:
#         raise HTTPException(
#             status_code=400,
#             detail="Unsupported webhook event.",
#         )

#     if event_header == "webhook.test":
#         return {
#             "success": True,
#             "message": "Webhook test received successfully.",
#         }

#     # 8. Acknowledge event
#     return {
#         "success": True,
#         "message": "Webhook received successfully.",
#         "event": event_header,
#     }


# @router.post("/voizematic")
# async def receive_voizematic_webhook(
#     request: Request,
#     db: AsyncSession = Depends(get_db),
# ):
#     logger.info("========== VOIZEMATIC WEBHOOK STARTED ==========")

#     # 1. Read raw body
#     raw_body = await request.body()

#     logger.info("========== VOIZEMATIC WEBHOOK RECEIVED ==========")
#     logger.info("Webhook event header: %s", event_header)
#     logger.info(
#         "Webhook body: %s",
#         raw_body.decode("utf-8", errors="replace"),
#     )

#     payload = json.loads(raw_body) if raw_body else {}

#     logger.info(
#         "Voizematic webhook payload: %s",
#         json.dumps(payload, indent=4, ensure_ascii=False),
#     )

#     # 2. Read headers
#     signature = request.headers.get("X-Voizematic-Signature")
#     event_header = request.headers.get("X-Voizematic-Event")

#     # 3. Log event and body
#     logger.info("Webhook event header: %s", event_header)
#     logger.info(
#         "Webhook body: %s",
#         raw_body.decode("utf-8", errors="replace"),
#     )
#     logger.info("Signature header received: %s", bool(signature))
#     logger.info("Content-Type: %s", request.headers.get("content-type"))

#     if not signature or not event_header:
#         logger.error("Missing webhook signature or event header.")
#         raise HTTPException(
#             status_code=401,
#             detail="Missing webhook signature or event header.",
#         )

#     # 4. Get active webhook registration
#     result = await db.execute(
#         select(ProviderWebhook).where(
#             ProviderWebhook.provider == "voizematic",
#             ProviderWebhook.provider_account_key == "default",
#             ProviderWebhook.is_active.is_(True),
#         )
#     )

#     webhook = result.scalar_one_or_none()

#     if not webhook or not webhook.webhook_secret_encrypted:
#         logger.error("Active webhook registration or secret not found.")
#         raise HTTPException(
#             status_code=401,
#             detail="Webhook registration not found.",
#         )

#     # 5. Decrypt secret
#     secret = decrypt_value(webhook.webhook_secret_encrypted)

#     # 6. Verify signature
#     expected_signature = hmac.new(
#         secret.encode("utf-8"),
#         raw_body,
#         digestmod="sha256",
#     ).hexdigest()

#     received_signature = signature.strip()

#     if received_signature.startswith("sha256="):
#         received_signature = received_signature[7:]

#     if not hmac.compare_digest(expected_signature, received_signature):
#         logger.error("Webhook signature verification failed.")
#         raise HTTPException(
#             status_code=401,
#             detail="Invalid webhook signature.",
#         )

#     logger.info("Webhook signature verified successfully.")

#     # 7. Parse JSON
#     try:
#         payload = json.loads(raw_body)
#     except json.JSONDecodeError:
#         logger.exception("Invalid webhook JSON payload.")
#         raise HTTPException(
#             status_code=400,
#             detail="Invalid webhook JSON payload.",
#         )

#     # 8. Check event
#     body_event = payload.get("event")

#     logger.info("Webhook event in body: %s", body_event)

#     if body_event and body_event != event_header:
#         logger.error(
#             "Event mismatch. Header=%s, Body=%s",
#             event_header,
#             body_event,
#         )
#         raise HTTPException(
#             status_code=400,
#             detail="Webhook event header does not match payload.",
#         )

#     if event_header == "webhook.test":
#         logger.info("Voizematic webhook test verified successfully.")

#         return {
#             "success": True,
#             "message": "Webhook test received and signature verified successfully.",
#         }

#     if event_header not in webhook.events:
#         logger.warning("Unsupported webhook event: %s", event_header)

#         raise HTTPException(
#             status_code=400,
#             detail="Unsupported webhook event.",
#         )

#         # Temporary diagnostic response: acknowledge test events
#         # only after signature verification.
#         # if event_header == "webhook.test":
#         #     return {
#         #         "success": True,
#         #         "message": "Webhook test received successfully.",
#         #     }

#         # raise HTTPException(
#         #     status_code=400,
#         #     detail="Unsupported webhook event.",
#         # )

#     logger.info("Webhook event accepted: %s", event_header)
#     logger.info("========== VOIZEMATIC WEBHOOK COMPLETED ==========")

#     return {
#         "success": True,
#         "message": "Webhook received successfully.",
#         "event": event_header,
#     }


@router.post("/voizematic")
async def receive_voizematic_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    logger.info("========== VOIZEMATIC WEBHOOK STARTED ==========")

    # 1. Read headers first
    signature = request.headers.get("X-Voizematic-Signature")
    event_header = request.headers.get("X-Voizematic-Event")

    logger.info("Webhook event header: %s", event_header)
    logger.info("Signature header received: %s", bool(signature))
    logger.info("Content-Type: %s", request.headers.get("content-type"))

    # 2. Read raw body
    raw_body = await request.body()

    logger.info("========== WEBHOOK RAW RESPONSE ==========")
    logger.info(
        "Webhook body:\n%s",
        raw_body.decode("utf-8", errors="replace"),
    )

    # 3. Parse JSON
    try:
        payload = json.loads(raw_body) if raw_body else {}
    except json.JSONDecodeError:
        logger.exception("Invalid webhook JSON payload.")
        raise HTTPException(
            status_code=400,
            detail="Invalid webhook JSON payload.",
        )

    # Print formatted JSON response
    logger.info(
        "========== FORMATTED VOIZEMATIC WEBHOOK DATA ==========\n%s",
        json.dumps(payload, indent=4, ensure_ascii=False),
    )

    # 4. Validate headers
    if not signature or not event_header:
        raise HTTPException(
            status_code=401,
            detail="Missing webhook signature or event header.",
        )

    # 5. Get active webhook registration
    result = await db.execute(
        select(ProviderWebhook).where(
            ProviderWebhook.provider == "voizematic",
            ProviderWebhook.provider_account_key == "default",
            ProviderWebhook.is_active.is_(True),
        )
    )

    webhook = result.scalar_one_or_none()

    if not webhook or not webhook.webhook_secret_encrypted:
        raise HTTPException(
            status_code=401,
            detail="Webhook registration not found.",
        )

    # 6. Verify signature
    secret = decrypt_value(webhook.webhook_secret_encrypted)

    expected_signature = hmac.new(
        secret.encode("utf-8"),
        raw_body,
        digestmod="sha256",
    ).hexdigest()

    received_signature = signature.strip()

    if received_signature.startswith("sha256="):
        received_signature = received_signature[7:]

    if not hmac.compare_digest(expected_signature, received_signature):
        logger.error("Webhook signature verification failed.")
        raise HTTPException(
            status_code=401,
            detail="Invalid webhook signature.",
        )

    logger.info("Webhook signature verified successfully.")

    # 7. Validate event
    body_event = payload.get("event")

    if body_event and body_event != event_header:
        raise HTTPException(
            status_code=400,
            detail="Webhook event header does not match payload.",
        )

    if event_header != "webhook.test" and event_header not in webhook.events:
        raise HTTPException(
            status_code=400,
            detail="Unsupported webhook event.",
        )

    logger.info("Webhook event accepted: %s", event_header)
    webhook_service = VoizematicWebhookService(db)

    if event_header == "call.created":
        await webhook_service.process_call_created(payload)

    elif event_header == "call.ended":
        await webhook_service.process_call_ended(payload)

    elif event_header == "call.failed":
        await webhook_service.process_call_failed(payload)

    elif event_header == "call.transcribed":
        await webhook_service.process_call_transcribed(payload)

    # 8. Acknowledge webhook
    logger.info("========== VOIZEMATIC WEBHOOK COMPLETED ==========")

    return {
        "success": True,
        "message": "Webhook received successfully.",
        "event": event_header,
    }
