# QSLMaster

Download QSO from Wavelog platform for QSL card label preparation.

## Requirements

- Python 3.7+
- requests

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

### Example `config.json`:
```json
{
  "api_key": "your_api_key_here",
  "station_id": "A123A",
  "wavelog_url": "https://wavelog.example.com"
}
```

## Usage

### Download all contacts from Wavelog
```bash
python main.py --config config.json
```

### Download and filter by date range
```bash
# QSOs from 2024-01-01 onwards
python main.py --config config.json --from-date 2024-01-01

# QSOs only from 2024
python main.py --config config.json --from-date 2024-01-01 --to-date 2024-12-31

# QSOs from June 2024
python main.py --config config.json --from-date 2024-06-01 --to-date 2024-06-30
```

### Verbose mode (more information)
```bash
python main.py --config config.json --from-date 2024-01-01 --verbose
```

### Help
```bash
python main.py --help
```

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

## Wavelog API Documentation

More information about the Wavelog API is available here:
https://github.com/wavelog/wavelog/wiki/API

## Project Structure

```
QSLMaster/
├── main.py              # Main application entry point
├── config.py            # Configuration management module
├── api.py               # Wavelog API communication module
├── config.example.json  # Example configuration file
├── requirements.txt     # Project dependencies
└── README.md            # This file
```

## License

GPLv3
