from pydantic import BaseModel, Field


class RegisterExistingPhoneNumberRequest(BaseModel):
    phone_number: str = Field(
        min_length=8,
        max_length=20,
    )


class PurchasePhoneNumberRequest(BaseModel):
    phone_number: str = Field(
        min_length=8,
        max_length=20,
    )


class AssignPhoneNumberRequest(BaseModel):
    voice_agent_id: int = Field(gt=0)
