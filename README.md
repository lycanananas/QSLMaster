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

### Check API availability
```bash
python main.py --config config.json
```

### Verbose mode (more information)
```bash
python main.py --config config.json --verbose
```

### Help
```bash
python main.py --help
```

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
