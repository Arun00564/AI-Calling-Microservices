import asyncio
from datetime import datetime, timezone

from celery import shared_task
from sqlalchemy import and_, or_, select

from app.db.database import CeleryAsyncSessionLocal
from app.db.models.campaign import Campaign
from app.db.models.campaign_contact import CampaignContact
from app.db.models.customer import Customer
from app.db.models.voice_agent import VoiceAgent
from app.db.models.voice_call_queue import VoiceCallQueue

CAMPAIGN_BATCH_SIZE = 5
CONTACT_BATCH_SIZE = 100


def generate_campaign_call_data(customer, agent):
    """
    Generate call variables using customer details and the agent's input schema.

    Supports Plivo agents with a dynamic input_schema and
    Voizematic agents with an empty input_schema.
    """

    default_mapping = {
        "lead_name": customer.full_name,
        "name": customer.full_name,
        "full_name": customer.full_name,
        "country_code": customer.country_code,
        "phone_number": customer.mobile_number,
        "mobile_number": customer.mobile_number,
    }

    input_schema = agent.input_schema or []

    # Voizematic agents currently have an empty input_schema.
    if not input_schema:
        return {
            "lead_name": customer.full_name,
            "country_code": customer.country_code,
            "phone_number": customer.mobile_number,
        }

    call_data = {}

    for field in input_schema:
        key = field.get("key")
        required = field.get("required", False)

        if not key:
            continue

        # Use known customer-field mappings first.
        value = default_mapping.get(key)

        # Support additional schema keys matching Customer model attributes.
        if value is None and hasattr(customer, key):
            value = getattr(customer, key)

        if required and (value is None or value == ""):
            return None

        if value is not None:
            call_data[key] = value

    # Phone details are required by the existing call normalization logic.
    if not call_data.get("phone_number"):
        return None

    return call_data


async def _process_campaign_queue():
    now = datetime.now(timezone.utc)

    campaigns_processed = 0
    contacts_queued = 0
    contacts_skipped = 0

    async with CeleryAsyncSessionLocal() as db:

        # Find campaigns ready for processing.
        # IN_PROGRESS campaigns are included so remaining contacts
        # can be enqueued in subsequent batches.
        result = await db.execute(
            select(Campaign)
            .where(
                or_(
                    Campaign.status == Campaign.StatusChoices.QUEUED,
                    and_(
                        Campaign.status == Campaign.StatusChoices.SCHEDULED,
                        Campaign.schedule_type == Campaign.ScheduleChoices.SCHEDULED,
                        Campaign.scheduled_at <= now,
                    ),
                    Campaign.status == Campaign.StatusChoices.IN_PROGRESS,
                )
            )
            .order_by(
                Campaign.scheduled_at.asc().nulls_first(),
                Campaign.id.asc(),
            )
            .limit(CAMPAIGN_BATCH_SIZE)
            .with_for_update(skip_locked=True)
        )

        campaigns = result.scalars().all()

        for campaign in campaigns:

            # Validate that the campaign's agent still exists.
            agent = await db.get(VoiceAgent, campaign.voice_agent_id)

            if not agent or not agent.is_active:
                campaign.status = Campaign.StatusChoices.FAILED
                campaign.completed_at = now
                continue

            # Lock pending contacts to prevent duplicate queue records.
            contact_result = await db.execute(
                select(CampaignContact, Customer)
                .join(
                    Customer,
                    Customer.id == CampaignContact.customer_id,
                )
                .where(
                    CampaignContact.campaign_id == campaign.id,
                    CampaignContact.status == CampaignContact.StatusChoices.PENDING,
                    Customer.user_id == campaign.user_id,
                    Customer.deleted_at.is_(None),
                )
                .order_by(CampaignContact.id.asc())
                .limit(CONTACT_BATCH_SIZE)
                .with_for_update(
                    of=CampaignContact,
                    skip_locked=True,
                )
            )

            contact_rows = contact_result.all()

            if campaign.started_at is None:
                campaign.started_at = now

            campaign.status = Campaign.StatusChoices.IN_PROGRESS

            campaign_queued_count = 0

            for campaign_contact, customer in contact_rows:

                call_data = generate_campaign_call_data(
                    customer=customer,
                    agent=agent,
                )

                # Required input data is missing.
                if not call_data:
                    campaign_contact.status = CampaignContact.StatusChoices.SKIPPED
                    contacts_skipped += 1
                    continue

                queue_item = VoiceCallQueue(
                    user_id=campaign.user_id,
                    voice_agent_id=campaign.voice_agent_id,
                    customer_id=customer.id,
                    campaign_id=campaign.id,
                    customer_list_id=campaign.customer_list_id,
                    # These identifiers are optional for now.
                    organisation_id=None,
                    product_id=None,
                    feature_id=None,
                    provider=(agent.provider or "plivo").lower(),
                    call_data=call_data,
                    source=VoiceCallQueue.SourceChoices.CAMPAIGN,
                    status=VoiceCallQueue.StatusChoices.PENDING,
                    priority=1,
                    scheduled_at=now,
                )

                db.add(queue_item)

                campaign_contact.status = CampaignContact.StatusChoices.QUEUED

                campaign_queued_count += 1

            campaign.queued_count += campaign_queued_count

            contacts_queued += campaign_queued_count
            campaigns_processed += 1

        await db.commit()

    return {
        "campaigns_processed": campaigns_processed,
        "contacts_queued": contacts_queued,
        "contacts_skipped": contacts_skipped,
    }


@shared_task(name="app.tasks.campaign_tasks.process_campaign_queue")
def process_campaign_queue():
    """
    Find due campaigns and add their pending contacts
    to the voice call queue.
    """

    return asyncio.run(_process_campaign_queue())
