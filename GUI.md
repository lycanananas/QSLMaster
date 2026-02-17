# QSLMaster GUI

Graphical User Interface for QSLMaster - makes QSL label generation easy and user-friendly.

## Features

- **Configuration Management**: Easy setup of Wavelog and QRZ credentials
- **Secure Credential Storage**: Uses system keyring for secure password storage
- **Date Filtering**: Download QSOs from specific date ranges
- **PDF Generation**: Automatically generate printable QSL labels
- **Live Progress Monitoring**: Real-time logging of processing steps
- **Background Processing**: Processing runs in separate thread, keeping UI responsive

## Installation

### Requirements
- Python 3.7+
- PyQt6 and dependencies (see requirements-gui.txt)

### Setup

1. Install GUI dependencies:
```bash
pip install -r requirements-gui.txt
```

2. Make the script executable:
```bash
chmod +x qslmaster_gui/main.py
```

## Usage

### Launch GUI

```bash
python qslmaster_gui/main.py
```

Or directly:
```bash
./qslmaster_gui/main.py
```

### Configuration Tab

1. Enter your **Wavelog URL** (e.g., `https://your-wavelog-instance.com`)
2. Enter your **API Key** from Wavelog
3. (Optional) Enter QRZ.com credentials for bureau verification
4. Click **Save Configuration**

Credentials are stored securely using your system's credential manager:
- **Linux**: libsecret (GNOME Keyring)
- **macOS**: Keychain
- **Windows**: Credential Manager

Configuration file is stored at:
- **Linux**: `~/.config/qslmaster/config.json`
- **macOS**: `~/Library/Application Support/qslmaster/config.json`
- **Windows**: `%APPDATA%\QSLMaster\config.json`

### Processing Tab

1. (Optional) Enable **Use date filter** and select date range
2. Verify output ADIF file path (or browse to select)
3. (Optional) Enable **Generate PDF Labels** and verify PDF path
4. (Optional) Check **Debug Labels** to draw borders for alignment checking
5. Click **Download & Process QSOs**

Monitor progress in the log output below.

## Security

### Credentials Security

- **API Keys**: Stored in system keyring ✓
- **Passwords**: Stored in system keyring ✓
- **Config File**: Readable only by user (0600 permissions) ✓
- **Logs**: Can be viewed at `~/.local/share/qslmaster/gui.log`

### No Hardcoded Secrets

All sensitive data is:
- Never written to configuration JSON
- Never logged to console or files
- Always stored in system keyring when possible

## CLI vs GUI

Both CLI and GUI share the same core processing logic:

```bash
# Old CLI (still works)
python qslmaster_cli.py --config config.json -o output.adif --generate-pdf labels.pdf

# New GUI
python qslmaster_gui/main.py
```

## Architecture

```
qslmaster_core.py          # Core processing logic (shared)
├── QSLProcessor class
└── All processing functions

qslmaster_cli.py           # CLI wrapper
└── Calls QSLProcessor

qslmaster_gui/
├── main.py                # Entry point
├── ui/
│   └── main_window.py     # Main window, tabs, dialogs
├── workers/
│   ├── signals.py         # Qt signals
│   └── processor_worker.py # Background worker
└── utils/
    ├── config_manager.py  # Config handling
    └── keyring_handler.py # Keyring integration
```

## Troubleshooting

### "Keyring not available"

If you see this warning, install keyring backend:

**Linux (GNOME)**:
```bash
sudo apt-get install gnome-keyring dbus-user-session
```

**Linux (KDE)**:
```bash
sudo apt-get install kwalletmanager
```

**macOS**:
- Keychain is built-in

**Windows**:
- Credential Manager is built-in

### Cache Issues

If you encounter country file issues, clear the cache:
```bash
rm -rf ~/.cache/qslmaster/
```

The country file will be downloaded again on next run.

## Development

To extend the GUI:

1. **Add new processing options**: Edit `qslmaster_gui/ui/main_window.py`
2. **Add new API calls**: Update `qslmaster_core.py` (shared with CLI)
3. **Change processing logic**: Modify `qslmaster_core.py::QSLProcessor`

## License

Same as QSLMaster
