import re


def extract_homecall(callsign: str) -> str:
    callsign = callsign.upper()
    parts = callsign.split('/')
    pattern = r'[0-9]?[A-Z]{1,2}[0-9](?:[A-Z]{1,4}|[0-9]{3}|[0-9]{1,3}[A-Z])[A-Z]{0,5}'
    return next((p for p in parts if re.fullmatch(pattern, p)), max(parts, key=len))


if __name__ == '__main__':
    tests = [
        ('SP5ABC', 'SP5ABC'),
        ('SP/SP5ABC', 'SP5ABC'),
        ('SP5ABC/W5', 'SP5ABC'),
        ('DL/SQ5FOX/M/DL', 'SQ5FOX'),
        ('3z3z3z', '3Z3Z3Z'),
        ('DL/3z3z3z', '3Z3Z3Z'),
        ('DL/3z3z3z/am/m/ok', '3Z3Z3Z'),
        ('N0CALL/P', 'N0CALL'),
        ('W5/N0CALL', 'N0CALL'),
        ('PJ4/SP0NULL/AM/QRP', 'SP0NULL'),
    ]
    
    for input_call, expected in tests:
        result = extract_homecall(input_call)
        status = '✓' if result == expected else '✗'
        print(f'{status} {input_call:20} -> {result:10} (expected: {expected})')
