import re


def extract_homecall(callsign: str) -> str:
    callsign = callsign.upper()
    parts = callsign.split('/')
    pattern = r'[0-9]?[A-Z]{1,2}[0-9](?:[A-Z]{1,4}|[0-9]{3}|[0-9]{1,3}[A-Z])[A-Z]{0,5}'
    return next((p for p in parts if re.fullmatch(pattern, p)), max(parts, key=len))

