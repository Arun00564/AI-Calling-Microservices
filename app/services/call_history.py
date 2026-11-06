from datetime import datetime, timedelta, timezone, time
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select, func, or_, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.customer import Customer
from app.db.models.voice_agent import VoiceAgent
from app.db.models.voice_call_logs import VoiceCallLog


class CallHistoryService:

    CONNECTED_STATUSES = ("completed", "answered", "connected")
    MISSED_STATUSES = ("missed", "no_answer", "no-answer", "busy")
    FAILED_STATUSES = ("failed",)

    def __init__(self, db: AsyncSession, current_user):
        self.db = db
        self.current_user = current_user

    @staticmethod
    def format_duration(seconds: int | None) -> str:
        seconds = max(int(seconds or 0), 0)
        minutes, remaining_seconds = divmod(seconds, 60)
        return f"{minutes}:{remaining_seconds:02d}"

    @staticmethod
    def get_date_range(
        period: str | None,
        start_date,
        end_date,
    ):
        now = datetime.now(timezone.utc)

        if start_date or end_date:
            start = (
                datetime.combine(start_date, time.min, tzinfo=timezone.utc)
                if start_date
                else None
            )
            end = (
                datetime.combine(
                    end_date + timedelta(days=1),
                    time.min,
                    tzinfo=timezone.utc,
                )
                if end_date
                else None
            )
            return start, end

        if period == "today":
            return (
                datetime.combine(now.date(), time.min, tzinfo=timezone.utc),
                None,
            )

        if period == "7days":
            return now - timedelta(days=7), None

        if period == "30days":
            return now - timedelta(days=30), None

        return None, None

    @staticmethod
    def normalize_status(value: str | None) -> str:
        return (value or "").strip().lower().replace(" ", "_")

    @staticmethod
    def serialize_transcription(value: Any):
        # Providers may return plain text or structured JSON.
        # Preserve the original data instead of inventing speakers.
        return value

    async def get_call_history(
        self,
        page: int = 1,
        page_size: int = 10,
        search: str | None = None,
        period: str | None = "7days",
        start_date=None,
        end_date=None,
        status: str | None = None,
        agent_id: int | None = None,
        direction: str | None = None,
        customer_id: int | None = None,
    ):
        filters = [
            VoiceCallLog.user_id == self.current_user.id,
        ]

        start, end = self.get_date_range(period, start_date, end_date)

        if start:
            filters.append(VoiceCallLog.created_at >= start)

        if end:
            filters.append(VoiceCallLog.created_at < end)

        if search and search.strip():
            term = f"%{search.strip()}%"

            filters.append(
                or_(
                    Customer.full_name.ilike(term),
                    Customer.mobile_number.ilike(term),
                    VoiceCallLog.to_number.ilike(term),
                    VoiceCallLog.call_status.ilike(term),
                )
            )

        if status:
            filters.append(
                func.lower(VoiceCallLog.call_status) == self.normalize_status(status)
            )

        if agent_id:
            filters.append(VoiceCallLog.voice_agent_id == agent_id)

        if direction:
            filters.append(func.lower(VoiceCallLog.direction) == direction.lower())

        if customer_id:
            filters.append(VoiceCallLog.customer_id == customer_id)

        # Common query, used for counts and listing.
        base_query = (
            select(VoiceCallLog)
            .outerjoin(
                Customer,
                Customer.id == VoiceCallLog.customer_id,
            )
            .where(*filters)
        )

        # Statistics reflect the selected filters.
        status_value = func.lower(VoiceCallLog.call_status)
        direction_value = func.lower(VoiceCallLog.direction)

        stats_query = (
            select(
                func.count(VoiceCallLog.id).label("total_calls"),
                func.count(VoiceCallLog.id)
                .filter(status_value.in_(self.CONNECTED_STATUSES))
                .label("connected"),
                func.avg(VoiceCallLog.call_duration)
                .filter(status_value.in_(self.CONNECTED_STATUSES))
                .label("avg_duration"),
                func.count(VoiceCallLog.id)
                .filter(direction_value == "inbound")
                .label("inbound"),
                func.count(VoiceCallLog.id)
                .filter(direction_value == "outbound")
                .label("outbound"),
                func.count(VoiceCallLog.id)
                .filter(status_value.in_(self.MISSED_STATUSES + self.FAILED_STATUSES))
                .label("missed_or_failed"),
            )
            .outerjoin(
                Customer,
                Customer.id == VoiceCallLog.customer_id,
            )
            .where(*filters)
        )

        stats_result = await self.db.execute(stats_query)
        stats = stats_result.one()

        total_calls = stats.total_calls or 0
        connected = stats.connected or 0
        avg_duration = round(float(stats.avg_duration or 0))

        # Fetch paginated call records.
        result = await self.db.execute(
            base_query.order_by(
                VoiceCallLog.created_at.desc(),
                VoiceCallLog.id.desc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        calls = result.scalars().all()

        customer_ids = {
            call.customer_id for call in calls if call.customer_id is not None
        }

        agent_ids = {
            call.voice_agent_id for call in calls if call.voice_agent_id is not None
        }

        customers = {}
        agents = {}

        if customer_ids:
            customer_result = await self.db.execute(
                select(Customer).where(
                    Customer.id.in_(customer_ids),
                    Customer.user_id == self.current_user.id,
                )
            )
            customers = {
                customer.id: customer for customer in customer_result.scalars().all()
            }

        if agent_ids:
            agent_result = await self.db.execute(
                select(VoiceAgent).where(
                    VoiceAgent.id.in_(agent_ids),
                    VoiceAgent.user_id == self.current_user.id,
                )
            )
            agents = {agent.id: agent for agent in agent_result.scalars().all()}

        items = []

        for call in calls:
            customer = customers.get(call.customer_id)
            agent = agents.get(call.voice_agent_id)

            items.append(
                {
                    "id": call.id,
                    "flow_run_uuid": call.flow_run_uuid,
                    "customer_id": call.customer_id,
                    "customer_name": (customer.full_name if customer else None),
                    "mobile_number": (
                        customer.mobile_number if customer else call.to_number
                    ),
                    "country_code": (customer.country_code if customer else None),
                    "agent_id": call.voice_agent_id,
                    "agent_name": agent.name if agent else None,
                    "provider": call.provider,
                    "direction": call.direction,
                    "call_status": call.call_status,
                    "call_duration": call.call_duration,
                    "duration_display": self.format_duration(call.call_duration),
                    "created_at": call.created_at,
                }
            )

        return {
            "statistics": {
                "total_calls": total_calls,
                "connected": connected,
                "connected_percentage": (
                    round(connected / total_calls * 100, 2) if total_calls else 0
                ),
                "average_duration_seconds": avg_duration,
                "average_duration_display": (self.format_duration(avg_duration)),
                "inbound": stats.inbound or 0,
                "outbound": stats.outbound or 0,
                "missed_or_failed": stats.missed_or_failed or 0,
            },
            "calls": items,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_records": total_calls,
                "total_pages": (
                    (total_calls + page_size - 1) // page_size if total_calls else 0
                ),
            },
        }

    async def get_call_details(self, call_log_id: int):
        result = await self.db.execute(
            select(VoiceCallLog).where(
                VoiceCallLog.id == call_log_id,
                VoiceCallLog.user_id == self.current_user.id,
            )
        )

        call = result.scalar_one_or_none()

        if not call:
            raise HTTPException(
                status_code=404,
                detail="Call log not found.",
            )

        customer = None
        agent = None

        if call.customer_id:
            customer_result = await self.db.execute(
                select(Customer).where(
                    Customer.id == call.customer_id,
                    Customer.user_id == self.current_user.id,
                )
            )
            customer = customer_result.scalar_one_or_none()

        if call.voice_agent_id:
            agent_result = await self.db.execute(
                select(VoiceAgent).where(
                    VoiceAgent.id == call.voice_agent_id,
                    VoiceAgent.user_id == self.current_user.id,
                )
            )
            agent = agent_result.scalar_one_or_none()

        return {
            "id": call.id,
            "customer": (
                {
                    "id": customer.id,
                    "full_name": customer.full_name,
                    "mobile_number": customer.mobile_number,
                    "country_code": customer.country_code,
                    "email": customer.email,
                }
                if customer
                else None
            ),
            "call_details": {
                "provider": call.provider,
                "provider_call_id": call.provider_call_id,
                "flow_run_uuid": call.flow_run_uuid,
                "call_status": call.call_status,
                "direction": call.direction,
                "from_number_id": call.from_number_id,
                "to_number": call.to_number,
                "agent_id": call.voice_agent_id,
                "agent_name": agent.name if agent else None,
                "started_at": call.created_at,
                "duration_seconds": call.call_duration,
                "duration_display": self.format_duration(call.call_duration),
                "hangup_source": call.hangup_source,
            },
            "conversation": {
                "summary": call.conversation_summary,
                "transcription": self.serialize_transcription(call.transcription),
            },
            "recording": {
                "url": call.recording_url,
                "duration_seconds": call.recording_duration,
                "duration_display": self.format_duration(call.recording_duration),
            },
            "additional_data": {
                "call_variables": call.call_variables,
            },
        }
