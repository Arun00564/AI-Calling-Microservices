from app.utils.voice_call import normalize_hangup_data

BASE_COLUMNS = [
    {"key": "mobile_number", "label": "Mobile Number"},
    {"key": "name", "label": "Name"},
    {"key": "call_status", "label": "Call Status"},
    {"key": "duration", "label": "Duration"},
    {"key": "call_end_reason", "label": "Call End Reason"},
    {"key": "conversation_id", "label": "Conversation ID"},
    {"key": "created_at", "label": "Created At"},
    {"key": "call_summary", "label": "Call Summary"},
    {"key": "transcript", "label": "Transcript"},
    {"key": "email", "label": "Email"},
]


BASE_COLUMN_MAPPING = {
    "mobile_number": lambda obj: (
        obj.customer.mobile_number if obj.customer else obj.to_number or ""
    ),
    "name": lambda obj: (obj.customer.full_name if obj.customer else ""),
    "call_status": lambda obj: obj.call_status or "",
    "duration": lambda obj: (
        obj.call_duration if obj.call_duration is not None else ""
    ),
    "call_end_reason": lambda obj: (
        normalize_hangup_data(obj.hangup_data or {}).get("call_status", "")
    ),
    "conversation_id": lambda obj: (
        normalize_hangup_data(obj.hangup_data or {}).get("conversation_id", "")
    ),
    "created_at": lambda obj: (
        obj.created_at.strftime("%Y-%m-%d %H:%M:%S") if obj.created_at else ""
    ),
    "call_summary": lambda obj: (obj.conversation_summary or ""),
    "transcript": lambda obj: (obj.transcription or ""),
    "email": lambda obj: (obj.customer.email if obj.customer else ""),
}
