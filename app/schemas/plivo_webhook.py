from typing import Any

from pydantic import BaseModel, ConfigDict


class PlivoWebhookObject(BaseModel):
    model_config = ConfigDict(extra="allow")

    call_uuid: str | None = None
    event_name: str | None = None
    event_data: dict[str, Any] = {}
    flow_run_uuid: str | None = None
    flow_uuid: str | None = None
    flow_name: str | None = None


class PlivoWebhookData(BaseModel):
    model_config = ConfigDict(extra="allow")

    object: PlivoWebhookObject | None = None


class PlivoWebhookPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    data: PlivoWebhookData | None = None
