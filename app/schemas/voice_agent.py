from pydantic import BaseModel, Field


class ToggleWhatsAppRequest(BaseModel):
    enabled: bool


class VoiceCallExcelDataRequest(BaseModel):
    columns: list[str]


class AssignVoiceNumberRequest(BaseModel):
    voice_number_id: int = Field(..., gt=0)


class VoizematicAgentUpdateRequest(BaseModel):
    name: str | None = None
    system_prompt: str | None = None
    greeting: str | None = None
    voice: str | None = None
    booking_url: str | None = None
