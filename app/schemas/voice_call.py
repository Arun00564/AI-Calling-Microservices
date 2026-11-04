from typing import Any

from pydantic import BaseModel, Field

# class StartCallRequest(BaseModel):
#     customer_id: int | None = None

#     call_data: dict[str, Any] = Field(default_factory=dict)


class StartCallRequest(BaseModel):
    customer_id: int | None = None
    call_data: dict[str, Any] = Field(default_factory=dict)

    organisation_id: str
    product_id: str
    feature_id: str

    # Voizematic optional fields
    knowledge_base_id: int | None = None
    context: str | None = None


class StartCallData(BaseModel):
    flow_run_uuid: str | None = None
    call_data: dict[str, Any]


class StartCallResponse(BaseModel):
    status: int
    message: str
    success: bool
    data: StartCallData | None = None


class AgentInputField(BaseModel):
    key: str
    label: str | None = None
    required: bool = False
