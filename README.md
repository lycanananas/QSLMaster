# QSLMaster

Download QSO from Wavelog platform for QSL card label preparation.

## Requirements

- Python 3.7+
- requests >= 2.28.0
- adif-io >= 0.2.5
- pyhamtools >= 0.12.0
- reportlab >= 4.0.0

## Installation

1. Clone the repository:
```bash
cd QSLMaster
```

2. Create virtual environment:
```bash
python3 -m venv venv
```

3. Activate virtual environment:
```bash
# On Linux/macOS:
source venv/bin/activate

# On Windows:
venv\Scripts\activate
```

4. Install dependencies:
```bash
pip install -r requirements.txt
```

## Configuration

1. Copy `config.example.json` to `config.json`:
```bash
cp config.example.json config.json
```

2. Edit `config.json` and fill in:
   - `api_key`: Your API key from Wavelog
   - `station_id`: Your station ID in Wavelog
   - `wavelog_url`: URL of your Wavelog instance (e.g., https://your-wavelog-instance.com)
   - `qrz_username`: Your QRZ.com username (premium account required for bureau verification)
   - `qrz_password`: Your QRZ.com password

### Example `config.json`:
```json
{
  "api_key": "your_api_key_here",
  "station_id": "A123A",
  "wavelog_url": "https://wavelog.example.com",
  "qrz_username": "your_qrz_username",
  "qrz_password": "your_qrz_password"
}
```

**Note**: QRZ.com credentials are optional. If not provided, the tool will skip QSL bureau verification for non-Poland stations.

## Usage

### Download all contacts from Wavelog
```bash
python qslmaster.py --config config.json
```

### Download and filter by date range
```bash
# QSOs from 2024-01-01 onwards
python qslmaster.py --config config.json --from-date 2024-01-01

# QSOs only from 2024
python qslmaster.py --config config.json --from-date 2024-01-01 --to-date 2024-12-31

# QSOs from June 2024
python qslmaster.py --config config.json --from-date 2024-06-01 --to-date 2024-06-30
```

### Verbose mode (more information)
```bash
python qslmaster.py --config config.json --from-date 2024-01-01 --verbose
```

### Help
```bash
python qslmaster.py --help
```

## Validating ADIF Output

After generating the ADIF file, validate its integrity:

```bash
python validate_adif.py qsl.adi
```

This tool:
- Verifies ADIF file format
- Shows total number of QSO records
- Displays ADIF version and program ID
- Lists all QSOs with CALL, date, QSL_SENT flag, and VIA field
- Helps identify any issues with the generated file

## Features

### ADIF Support
The application downloads contacts from Wavelog in ADIF format and parses them using the `adif-io` library. Key features:

- **Robust parsing**: Uses proven `adif-io` library for ADIF format support
- **Date/Time handling**: Extracts QSO_DATE and TIME_ON fields from ADIF records
- **Statistics**: Shows date range, number of countries/DXCC, and summary information

### Date Range Filtering
Filter downloaded contacts by date range:

- Use `--from-date` to include only QSOs on or after a specific date
- Use `--to-date` to include only QSOs on or before a specific date
- Date format: `YYYY-MM-DD` (e.g., 2024-06-15)

The filtered QSO data is prepared for further processing such as label generation.

### QSL Bureau Verification
The application verifies QSL bureau availability for non-Poland QSOs using QRZ.com premium API:

- **QRZ Integration**: Queries QRZ.com to check if a station has a QSL bureau manager
- **Flexible Detection**: Recognizes various bureau descriptions (Polish: biuro/bureau, German: büro, French: agence, etc.)
- **Case Insensitive**: Handles different formatting and capitalization of bureau information
- **Error Handling**: Gracefully handles lookup failures without stopping the entire process

### Country-Specific Processing
- **Poland (SP)**: Queries PZK (Polish Radio Amateur Union) database to find OT- bureau routes
- **Other Countries**: Uses QRZ.com API to identify stations with QSL bureau managers

## API Documentation

More information about the APIs used:

- **Wavelog API**: https://github.com/wavelog/wavelog/wiki/API
- **QRZ.com XML API**: https://www.qrz.com/page/api (premium account required)

## Project Structure

```
QSLMaster/
├── qslmaster.py         # Main application entry point
├── config.py            # Configuration management module
├── wavelog.py           # Wavelog API communication module
├── qrz.py               # QRZ.com API module for QSL bureau verification
├── poland.py            # Poland DXCC processing (PZK member verification)
├── other.py             # Other countries processing (QRZ bureau verification)
├── validate_adif.py     # ADIF file validator
├── config.example.json  # Example configuration file
├── requirements.txt     # Project dependencies
└── README.md            # This file
```

## License

QSLMaster is distributed under the **GNU General Public License v3.0**.

This means you are free to use, modify, and distribute this software, but you must:
- Include the license and copyright notice
- Document any changes you make
- Disclose the source code when you distribute it
- Use the same license for any derivative works

For details, see [LICENSE.md](LICENSE.md) or visit https://www.gnu.org/licenses/gpl-3.0.en.html

## Contributing

Contributions are welcome! Feel free to submit issues and pull requests.

## Support

For issues, questions, or feature requests, please open an issue on the project repository.
