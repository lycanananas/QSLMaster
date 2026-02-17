import sys
import argparse
from pathlib import Path
import adif_io


def validate_adif(filepath: str) -> None:
    file_path = Path(filepath)
    
    if not file_path.exists():
        print(f"Error: {filepath} not found")
        sys.exit(1)
    
    try:
        with open(file_path, 'r', encoding='UTF-8') as f:
            content = f.read()
        
        qsos, headers = adif_io.read_from_string(content)
        
        print(f"✓ Valid ADIF file")
        print(f"  QSOs: {len(qsos)}")
        print(f"  ADIF Version: {headers.get('ADIF_VER', 'N/A')}")
        print(f"  Program ID: {headers.get('PROGRAMID', 'N/A')}")
        
        if not qsos:
            print("\n⚠ Warning: No QSO records found")
            return
        
        print(f"\nAll {len(qsos)} QSOs:")
        for i, qso in enumerate(qsos, 1):
            call = qso.get('CALL', 'N/A')
            date = qso.get('QSO_DATE', 'N/A')
            qsl_sent = qso.get('QSL_SENT', 'N/A')
            qsl_sent_via = qso.get('QSL_SENT_VIA', 'N/A')
            qsl_via = qso.get('QSL_VIA', 'N/A')
            print(f"  {i}. {call} ({date}) - QSL_SENT: {qsl_sent} - SENT_VIA: {qsl_sent_via} - VIA: {qsl_via}")
        
        print(f"\n✓ File structure looks correct")
        
    except Exception as e:
        print(f"✗ Error validating ADIF: {e}")
        sys.exit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Validate ADIF file format and display QSO records')
    parser.add_argument('file', nargs='?', default='qsl.adi', help='Path to ADIF file (default: qsl.adi)')
    args = parser.parse_args()
    validate_adif(args.file)
