from pydantic import BaseModel, Field, EmailStr, ConfigDict
from typing import Optional


class ManualCustomerRequest(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=100)
    email: Optional[EmailStr] = None
    country_code: Optional[str] = Field(None, max_length=5)
    mobile_number: str = Field(..., min_length=1, max_length=20)


class ManualCustomerListRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    tags: Optional[list[str]] = None
    contacts: list[ManualCustomerRequest] = Field(..., min_length=1)

    model_config = ConfigDict(str_strip_whitespace=True)
