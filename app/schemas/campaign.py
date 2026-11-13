from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class CreateCampaignRequest(BaseModel):

    name: str = Field(min_length=1, max_length=150)

    voice_agent_id: int

    customer_list_id: int

    schedule_type: Literal["NOW", "SCHEDULED"] = "NOW"

    scheduled_at: datetime | None = None

    @model_validator(mode="after")
    def validate_schedule(self):

        if self.schedule_type == "SCHEDULED":

            if not self.scheduled_at:
                raise ValueError("Scheduled date and time are required.")

            if self.scheduled_at.tzinfo is None:
                raise ValueError("Timezone information is required.")

            if self.scheduled_at.minute not in (0, 15, 30, 45):
                raise ValueError("Campaign time must use 15-minute intervals.")

            if self.scheduled_at.second != 0:
                raise ValueError("Seconds must be zero.")

        else:
            self.scheduled_at = None

        return self
