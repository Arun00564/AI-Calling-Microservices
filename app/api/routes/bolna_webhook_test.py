from fastapi import APIRouter, Request
import json

router = APIRouter(
    prefix="/api/v1/webhooks/test",
    tags=["Webhooks"],
)


# @router.post("/bolna")
# async def bolna_webhook(request: Request):
#     payload = await request.json()

#     print("\n========== BOLNA WEBHOOK ==========")
#     print(payload)
#     print("===================================\n")

#     return {"success": True, "message": "Webhook received"}


@router.post("/voizematic")
async def voizematics_webhook(request: Request):
    raw_body = await request.body()

    print("\n========== VOIZEMATIC WEBHOOK ==========")
    print("Headers:", dict(request.headers))
    print("Raw body:", raw_body.decode("utf-8", errors="replace"))

    try:
        payload = json.loads(raw_body) if raw_body else {}
    except json.JSONDecodeError:
        payload = {"raw_body": raw_body.decode("utf-8", errors="replace")}

    print("Payload:", payload)
    print("========================================\n")

    return {
        "success": True,
        "message": "Webhook received",
    }
