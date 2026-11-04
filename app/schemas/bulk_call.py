from typing import Any

from pydantic import BaseModel


class BulkCallRequest(BaseModel):
    organisation_id: str
    product_id: str
    feature_id: str
    agent_id: int

    leads: list[dict[str, Any]]
