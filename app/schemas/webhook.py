from pydantic import BaseModel, HttpUrl
from typing import Literal


class VoizematicWebhookRegisterRequest(BaseModel):
    url: HttpUrl

    events: list[
        Literal[
            "call.created",
            "call.ended",
            "call.failed",
            "call.transcribed",
        ]
    ] = [
        "call.created",
        "call.ended",
        "call.failed",
        "call.transcribed",
    ]
