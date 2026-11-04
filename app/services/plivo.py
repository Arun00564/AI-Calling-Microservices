import base64

import httpx

from app.core.config import settings


class PlivoVoiceService:
    """
    Service responsible for communicating with Plivo Agent Flow API.
    """

    def __init__(self, flow_id: str):
        self.auth_id = settings.PLIVO_AUTH_ID
        self.auth_token = settings.PLIVO_AUTH_TOKEN
        self.base_url = settings.PLIVO_AGENT_FLOW_BASE_URL
        self.flow_id = flow_id

    def _build_flow_url(self) -> str:
        return f"{self.base_url}/" f"{self.auth_id}/flow/" f"{self.flow_id}"

    def _get_headers(self) -> dict:
        auth_string = f"{self.auth_id}:{self.auth_token}"

        encoded_auth = base64.b64encode(auth_string.encode()).decode()

        return {
            "Authorization": f"Basic {encoded_auth}",
            "Content-Type": "application/json",
        }

    async def trigger_flow_call(
        self,
        variables: dict,
    ) -> dict:

        variables = variables or {}

        try:

            async with httpx.AsyncClient(timeout=30.0) as client:

                response = await client.post(
                    self._build_flow_url(),
                    json=variables,
                    headers=self._get_headers(),
                )

            response_json = response.json()

            print(
                "Plivo response:",
                response_json,
            )

            if not response.is_success:
                return {
                    "success": False,
                    "status_code": response.status_code,
                    "error": response_json,
                    "flow_id_used": self.flow_id,
                    "payload_sent": variables,
                }

            return {
                "success": True,
                "status_code": response.status_code,
                "response_json": response_json,
                "response_text": response.text,
                "flow_id_used": self.flow_id,
                "payload_sent": variables,
            }

        except httpx.TimeoutException:

            return {
                "success": False,
                "error": "Plivo API request timed out.",
                "flow_id_used": self.flow_id,
            }

        except httpx.HTTPError as e:

            return {
                "success": False,
                "error": str(e),
                "flow_id_used": self.flow_id,
            }

        except Exception as e:

            return {
                "success": False,
                "error": str(e),
                "flow_id_used": self.flow_id,
            }
