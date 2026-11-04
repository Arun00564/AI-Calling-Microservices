import json
import asyncio

from app.db.database import SyncSessionLocal
from app.db.models.user_details import UserDetails
from app.db.models.voice_agent import VoiceAgent
from app.db.models.customer import Customer
from app.db.models.voice_call_logs import VoiceCallLog
from app.services.plivo import PlivoVoiceService

from app.tasks.celery_app import celery_app


@celery_app.task
def test_voice_task(message: str):
    print("VOICE TASK EXECUTED:", message)

    return {
        "success": True,
        "message": message,
    }


@celery_app.task
def process_completed_call_task(
    call_log_id: int,
):
    print(f"Starting post-call processing: {call_log_id}")

    return asyncio.run(_process_completed_call(call_log_id))


async def _process_completed_call(
    call_log_id: int,
):

    from app.db.database import AsyncSessionLocal
    from app.services.call_processing import (
        CallProcessingService,
    )

    async with AsyncSessionLocal() as db:

        service = CallProcessingService(db=db)

        return await service.process_completed_call(call_log_id=call_log_id)
    # IMPORTANT:
    # Celery task is synchronous.
    # Our database service is async.


@celery_app.task
def initiate_bulk_voice_call(
    user_detail_id: int,
    agent_id: int,
    call_data: dict,
    organisation_id: str,
    product_id: str,
    feature_id: str,
):
    db = SyncSessionLocal()

    try:
        # ==========================================
        # User
        # ==========================================

        user_detail = (
            db.query(UserDetails)
            .filter(
                UserDetails.id == user_detail_id,
                UserDetails.is_active.is_(True),
            )
            .first()
        )

        if not user_detail:
            return {
                "success": False,
                "error": "User not found",
            }

        # ==========================================
        # Agent
        # ==========================================

        agent = (
            db.query(VoiceAgent)
            .filter(
                VoiceAgent.id == agent_id,
                VoiceAgent.user_id == user_detail.id,
                VoiceAgent.is_active.is_(True),
            )
            .first()
        )

        if not agent:
            return {
                "success": False,
                "error": "Agent not found or inactive",
            }

        # ==========================================
        # Extract common fields
        # ==========================================

        lead_name = call_data.get("lead_name") or call_data.get("customer_name") or ""

        email = call_data.get("email")

        phone_number = str(call_data.get("phone_number", "")).strip()

        # ==========================================
        # Customer create/update
        # ==========================================

        customer = (
            db.query(Customer)
            .filter(
                Customer.mobile_number == phone_number,
                Customer.user_id == user_detail.id,
            )
            .first()
        )

        if not customer:

            customer = Customer(
                user_id=user_detail.id,
                full_name=lead_name,
                email=email,
                mobile_number=phone_number,
                status="ACTIVE",
            )

            db.add(customer)
            db.flush()

        else:

            if lead_name:
                customer.full_name = lead_name

            if email:
                customer.email = email

        # ==========================================
        # Trigger Plivo
        # ==========================================

        plivo_service = PlivoVoiceService(flow_id=agent.plivo_agent_id)

        plivo_response = plivo_service.trigger_flow_call(variables=call_data)

        if not plivo_response.get("success"):

            db.rollback()

            return {
                "success": False,
                "phone_number": phone_number,
                "error": "Plivo call failed",
            }

        # ==========================================
        # Plivo response
        # ==========================================

        response_json = json.loads(
            plivo_response.get(
                "response_text",
                "{}",
            )
        )

        api_id = response_json.get("api_id")
        phlo_id = response_json.get("phlo_id")

        # ==========================================
        # Voice Call Log
        # ==========================================

        call_log = VoiceCallLog(
            flow_run_uuid=api_id,
            flow_uuid=phlo_id,
            voice_agent_id=agent.id,
            customer_id=customer.id,
            user_id=user_detail.id,
            from_number_id=agent.voice_number_id,
            to_number=phone_number,
            call_status="initiated",
            call_variables=call_data,
            organisation_id=organisation_id,
            product_id=product_id,
            feature_id=feature_id,
        )

        db.add(call_log)
        db.commit()

        return {
            "success": True,
            "phone_number": phone_number,
            "flow_run_uuid": api_id,
            "call_log_id": call_log.id,
        }

    except Exception as e:
        db.rollback()
        return {
            "success": False,
            "error": str(e),
        }

    finally:
        db.close()
