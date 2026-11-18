import asyncio
from datetime import datetime, timedelta, timezone

from celery import shared_task
from fastapi import HTTPException
from sqlalchemy import select

# from app.db.database import AsyncSessionLocal
from app.db.database import CeleryAsyncSessionLocal
from app.db.models.user_details import UserDetails
from app.db.models.voice_call_queue import VoiceCallQueue
from app.services.voice_call import VoiceCallService

BATCH_SIZE = 10
RETRY_BASE_SECONDS = 30


async def _claim_pending_queue_records() -> list[int]:
    """Atomically claim pending queue records."""

    now = datetime.now(timezone.utc)

    async with CeleryAsyncSessionLocal() as db:
        result = await db.execute(
            select(VoiceCallQueue)
            .where(
                VoiceCallQueue.status == VoiceCallQueue.StatusChoices.PENDING,
                VoiceCallQueue.scheduled_at <= now,
            )
            .order_by(
                VoiceCallQueue.priority.desc(),
                VoiceCallQueue.scheduled_at.asc(),
                VoiceCallQueue.id.asc(),
            )
            .limit(BATCH_SIZE)
            .with_for_update(skip_locked=True)
        )

        queue_items = result.scalars().all()
        queue_ids = []

        for item in queue_items:
            item.status = VoiceCallQueue.StatusChoices.PROCESSING
            item.processing_started_at = now
            queue_ids.append(item.id)

        await db.commit()

        return queue_ids


# @shared_task(name="app.tasks.voice_queue_tasks.process_voice_call_queue")
# def process_voice_call_queue():
#     """Find pending records and dispatch individual call tasks."""

#     queue_ids = asyncio.run(_claim_pending_queue_records())

#     dispatched = []

#     for queue_id in queue_ids:
#         try:
#             initiate_queued_voice_call.delay(queue_id)
#             dispatched.append(queue_id)

#         except Exception:
#             # If Celery cannot enqueue the task, release the record.
#             asyncio.run(_release_queue_record(queue_id))

#     return {
#         "claimed": len(queue_ids),
#         "dispatched": dispatched,
#     }


@shared_task(name="app.tasks.voice_queue_tasks.process_voice_call_queue")
def process_voice_call_queue():
    print("QUEUE DISPATCHER STARTED")

    queue_ids = asyncio.run(_claim_pending_queue_records())

    print("CLAIMED QUEUE IDS:", queue_ids)

    dispatched = []

    for queue_id in queue_ids:
        try:
            task = initiate_queued_voice_call.delay(queue_id)

            print(f"CALL TASK DISPATCHED: queue_id={queue_id}, " f"task_id={task.id}")

            dispatched.append(queue_id)

        except Exception as exc:
            print("TASK DISPATCH ERROR:", str(exc))
            asyncio.run(_release_queue_record(queue_id))

    print("DISPATCHER FINISHED:", dispatched)

    return {
        "claimed": len(queue_ids),
        "dispatched": dispatched,
    }


async def _release_queue_record(queue_id: int):
    """Return a claimed record to pending if task dispatch fails."""

    async with CeleryAsyncSessionLocal() as db:
        item = await db.get(VoiceCallQueue, queue_id)

        if item and item.status == VoiceCallQueue.StatusChoices.PROCESSING:
            item.status = VoiceCallQueue.StatusChoices.PENDING
            item.processing_started_at = None
            item.scheduled_at = datetime.now(timezone.utc) + timedelta(
                seconds=RETRY_BASE_SECONDS
            )
            item.error_message = "Celery task dispatch failed."

            await db.commit()


async def _initiate_queued_voice_call(queue_id: int):
    """Initiate one queued call using the existing VoiceCallService."""

    async with CeleryAsyncSessionLocal() as db:
        queue_item = await db.get(VoiceCallQueue, queue_id)

        if not queue_item:
            return {"success": False, "message": "Queue record not found."}

        # Ignore tasks for records that are no longer being processed.
        if queue_item.status != VoiceCallQueue.StatusChoices.PROCESSING:
            return {
                "success": False,
                "message": "Queue record is not in processing state.",
            }

        user = await db.get(UserDetails, queue_item.user_id)

        if not user:
            queue_item.status = VoiceCallQueue.StatusChoices.FAILED
            queue_item.error_message = "User not found."
            queue_item.completed_at = datetime.now(timezone.utc)
            await db.commit()

            return {"success": False, "message": "User not found."}

        # Count this as an attempt before contacting the provider.
        queue_item.attempt_count += 1
        await db.commit()

        try:
            service = VoiceCallService(
                db=db,
                current_user=user,
            )

            result = await service.start_call(
                agent_id=queue_item.voice_agent_id,
                customer_id=queue_item.customer_id,
                call_data=queue_item.call_data,
                organisation_id=queue_item.organisation_id,
                product_id=queue_item.product_id,
                feature_id=queue_item.feature_id,
                campaign_id=queue_item.campaign_id,
                customer_list_id=queue_item.customer_list_id,
            )

            if result.get("success") is False:
                raise RuntimeError(result.get("message", "Call initiation failed."))

            call_log_id = result.get("call_log_id")

            if not call_log_id:
                raise RuntimeError("Call was not created: call_log_id is missing.")

            # start_call() commits the VoiceCallLog. Refresh the queue row.
            await db.refresh(queue_item)

            queue_item.voice_call_log_id = call_log_id
            queue_item.status = VoiceCallQueue.StatusChoices.INITIATED
            queue_item.error_message = None

            await db.commit()

            return {
                "success": True,
                "queue_id": queue_id,
                "call_log_id": call_log_id,
                "provider": result.get("provider"),
            }

        except Exception as exc:
            await db.rollback()

            # Re-fetch after rollback.
            queue_item = await db.get(VoiceCallQueue, queue_id)

            if not queue_item:
                return {"success": False, "message": str(exc)}

            queue_item.error_message = str(exc)

            if queue_item.attempt_count < queue_item.max_attempts:
                # Exponential retry delay: 30s, 60s, 120s, ...
                retry_delay = RETRY_BASE_SECONDS * (
                    2 ** max(queue_item.attempt_count - 1, 0)
                )

                queue_item.status = VoiceCallQueue.StatusChoices.PENDING
                queue_item.processing_started_at = None
                queue_item.scheduled_at = datetime.now(timezone.utc) + timedelta(
                    seconds=retry_delay
                )

            else:
                queue_item.status = VoiceCallQueue.StatusChoices.FAILED
                queue_item.completed_at = datetime.now(timezone.utc)

            await db.commit()

            return {
                "success": False,
                "queue_id": queue_id,
                "attempt": queue_item.attempt_count,
                "error": str(exc),
                "status": queue_item.status,
            }


@shared_task(
    bind=True,
    name="app.tasks.voice_queue_tasks.initiate_queued_voice_call",
)
def initiate_queued_voice_call(self, queue_id: int):
    return asyncio.run(_initiate_queued_voice_call(queue_id))
