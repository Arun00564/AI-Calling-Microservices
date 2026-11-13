from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.voice_agent import VoiceAgent
from app.db.models.customer import Customer
from app.db.models.customer_list import CustomerList, CustomerListContact
from app.db.models.campaign import Campaign
from app.db.models.campaign_contact import CampaignContact


class CampaignService:

    def __init__(self, db: AsyncSession, current_user):
        self.db = db
        self.current_user = current_user

    async def create_campaign(self, request):

        try:
            # 1. Validate voice agent ownership
            agent_result = await self.db.execute(
                select(VoiceAgent).where(
                    VoiceAgent.id == request.voice_agent_id,
                    VoiceAgent.user_id == self.current_user.id,
                    VoiceAgent.is_active.is_(True),
                )
            )

            agent = agent_result.scalar_one_or_none()

            if not agent:
                raise HTTPException(
                    status_code=404,
                    detail="Voice agent not found or inactive.",
                )

            # 2. Validate customer list ownership
            list_result = await self.db.execute(
                select(CustomerList).where(
                    CustomerList.id == request.customer_list_id,
                    CustomerList.user_id == self.current_user.id,
                    CustomerList.status == "ACTIVE",
                )
            )

            customer_list = list_result.scalar_one_or_none()

            if not customer_list:
                raise HTTPException(
                    status_code=404,
                    detail="Customer list not found or inactive.",
                )

            # 3. Fetch unique active customers in this list
            contacts_result = await self.db.execute(
                select(Customer)
                .join(
                    CustomerListContact,
                    CustomerListContact.customer_id == Customer.id,
                )
                .where(
                    CustomerListContact.customer_list_id == customer_list.id,
                    Customer.user_id == self.current_user.id,
                    Customer.deleted_at.is_(None),
                )
                .distinct()
            )

            customers = contacts_result.scalars().all()

            if not customers:
                raise HTTPException(
                    status_code=400,
                    detail="This customer list has no active contacts.",
                )

            # 4. Validate scheduled time
            scheduled_at = None

            if request.schedule_type == "SCHEDULED":
                scheduled_at = request.scheduled_at.astimezone(timezone.utc)

                if scheduled_at <= datetime.now(timezone.utc):
                    raise HTTPException(
                        status_code=400,
                        detail="Scheduled time must be in the future.",
                    )

            # 5. Determine initial campaign status
            if request.schedule_type == "NOW":
                campaign_status = Campaign.StatusChoices.QUEUED
            else:
                campaign_status = Campaign.StatusChoices.SCHEDULED

            # 6. Create campaign
            campaign = Campaign(
                user_id=self.current_user.id,
                name=request.name.strip(),
                voice_agent_id=agent.id,
                customer_list_id=customer_list.id,
                schedule_type=request.schedule_type,
                scheduled_at=scheduled_at,
                status=campaign_status,
                total_contacts=len(customers),
            )

            self.db.add(campaign)
            await self.db.flush()

            # 7. Create one CampaignContact per unique customer
            campaign_contacts = [
                CampaignContact(
                    campaign_id=campaign.id,
                    customer_id=customer.id,
                    status=CampaignContact.StatusChoices.PENDING,
                )
                for customer in customers
            ]

            self.db.add_all(campaign_contacts)

            await self.db.commit()
            await self.db.refresh(campaign)

            return {
                "id": campaign.id,
                "name": campaign.name,
                "status": campaign.status,
                "schedule_type": campaign.schedule_type,
                "scheduled_at": campaign.scheduled_at,
                "voice_agent": {
                    "id": agent.id,
                    "name": agent.name,
                    "provider": agent.provider,
                },
                "customer_list": {
                    "id": customer_list.id,
                    "name": customer_list.name,
                },
                "total_contacts": campaign.total_contacts,
                "queued_count": campaign.queued_count,
                "created_at": campaign.created_at,
            }

        except Exception:
            await self.db.rollback()
            raise
