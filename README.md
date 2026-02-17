# QSLMaster

Download QSO data from Wavelog and prepare ADIF output and printable QSL labels. The project includes both a CLI and a GUI, sharing the same processing core.

## Features

- CLI and GUI based workflows
- ADIF download and parsing
- Date range filtering
- QSL bureau verification via QRZ.com (optional)
- Country specific processing for Poland (PZK lookup)
- PDF label generation
- Background processing and live progress in GUI

## Requirements

- Python 3.7+
- Wavelog 2.0.0 or higher
- CLI dependencies in requirements.txt
- GUI dependencies in requirements-gui.txt

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

4. Install CLI dependencies:
```bash
pip install -r requirements.txt
```

5. Install GUI dependencies (optional):
```bash
pip install -r requirements-gui.txt
```

## Configuration

### CLI configuration file

1. Copy config.example.json to config.json:
```bash
cp config.example.json config.json
```

2. Edit config.json and fill in:
   - api_key: Your API key from Wavelog
   - wavelog_url: URL of your Wavelog instance
   - qrz_username: Your QRZ.com username (optional)
   - qrz_password: Your QRZ.com password (optional)

Example config.json:
```json
{
  "api_key": "your_api_key_here",
  "wavelog_url": "https://wavelog.example.com",
  "qrz_username": "your_qrz_username",
  "qrz_password": "your_qrz_password"
}
```

QRZ.com credentials are optional. If not provided, bureau verification for non-Poland stations is skipped.

### GUI configuration and credentials

The GUI stores configuration in the user profile and keeps secrets in the system keyring.

Config file locations:
- Linux: ~/.config/qslmaster/config.json
- macOS: ~/Library/Application Support/qslmaster/config.json
- Windows: %APPDATA%\QSLMaster\config.json

Keyring backends:
- Linux: libsecret (GNOME Keyring) or KWallet
- macOS: Keychain
- Windows: Credential Manager

## Usage

### GUI

Launch the GUI:
```bash
python qslmaster_gui/main.py
```

### CLI

Download all contacts:
```bash
python qslmaster_cli/main.py --config config.json -o output.adif
```

Filter by date range:
```bash
python qslmaster_cli/main.py --config config.json --from-date 2024-01-01 --to-date 2024-12-31 -o output.adif
```

Generate PDF labels:
```bash
python qslmaster_cli/main.py --config config.json -o output.adif --generate-pdf labels.pdf
```

Help:
```bash
python qslmaster_cli/main.py --help
```

## Validating ADIF Output

After generating the ADIF file, validate its integrity:
```bash
python qslmaster_cli/validate_adif.py qsl.adi
```

## Troubleshooting

Keyring not available:
- Linux GNOME: sudo apt-get install gnome-keyring dbus-user-session
- Linux KDE: sudo apt-get install kwalletmanager

Cache issues:
```bash
rm -rf ~/.cache/qslmaster/
```

## API Documentation

- Wavelog API: https://github.com/wavelog/wavelog/wiki/API
- QRZ.com XML API: https://www.qrz.com/page/api

## Project Structure

```
QSLMaster/
├── qslmaster_cli/
│   ├── main.py
│   ├── config.py
│   ├── qslmaster_core.py
│   ├── wavelog.py
│   ├── qrz.py
│   ├── poland.py
│   ├── other.py
│   ├── pdf_labels.py
│   └── validate_adif.py
├── qslmaster_gui/
│   ├── main.py
│   ├── ui/
│   ├── dialogs/
│   ├── workers/
│   └── utils/
├── config.example.json
├── requirements.txt
├── requirements-gui.txt
└── README.md
```

## License

QSLMaster is distributed under the GNU General Public License v3.0. For details, see LICENSE.md or https://www.gnu.org/licenses/gpl-3.0.en.html

## Contributing

Contributions are welcome. Please open issues or pull requests.
