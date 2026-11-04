def normalize_hangup_data(hangup_data: dict) -> dict:
    normalized = {}

    for key, value in (hangup_data or {}).items():
        if "." not in key:
            continue

        field = key.split(".")[-1].strip().lower().replace(" ", "_")

        normalized[field] = value

    return normalized
