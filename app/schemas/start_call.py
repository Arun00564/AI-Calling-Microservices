from typing import Any

from pydantic import BaseModel, Field


class StartCallRequest(BaseModel):
    customer_id: int | None = None
    # call_data: dict[str, Any] = Field(default_factory=dict)
    organisation_id: str
    product_id: str
    feature_id: str
    agent_id: int
    payload: dict[str, Any]
