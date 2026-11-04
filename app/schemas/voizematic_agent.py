from pydantic import BaseModel, Field, ConfigDict
from typing import Literal


class VoizematicAgentCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    system_prompt: str = Field(..., min_length=1)
    greeting: str | None = None
    type: Literal["inbound", "outbound"] = "outbound"
    voice: str | None = None


# class VoizematicAgentUpdateRequest(BaseModel):
#     model_config = ConfigDict(extra="forbid")

#     name: str | None = None
#     system_prompt: str | None = None
#     greeting: str | None = None
# type: Literal["inbound", "outbound"] | None = None
#     voice: str | None = None
