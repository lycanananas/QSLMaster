import json
import sys
from pathlib import Path
from typing import Dict, Any


class ConfigError(Exception):
    pass


ALLOWED_SOURCES = {'wavelog', 'adif_file'}


def load_config(config_path: str) -> Dict[str, Any]:
    config_file = Path(config_path)
    
    if not config_file.exists():
        raise ConfigError(f"Configuration file not found: {config_path}")
    
    if not config_file.is_file():
        raise ConfigError(f"Configuration path is not a file: {config_path}")
    
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        raise ConfigError(f"Invalid JSON in configuration file: {e}")
    except IOError as e:
        raise ConfigError(f"Error reading configuration file: {e}")
    
    source = str(config.get('source', 'wavelog')).strip().lower()
    if source in {'adif', 'file'}:
        source = 'adif_file'
    config['source'] = source

    optional_fields = [
        'api_key',
        'wavelog_url',
        'adif_file_path',
        'qrz_username',
        'qrz_password',
        'logo_path',
        'ignored_dxcc',
    ]

    for field in optional_fields:
        if field not in config:
            if field == 'ignored_dxcc':
                config[field] = []
            else:
                config[field] = ''
    
    return config


def validate_config(config: Dict[str, Any]) -> bool:
    source = str(config.get('source', 'wavelog')).strip().lower()
    if source in {'adif', 'file'}:
        source = 'adif_file'
    if source not in ALLOWED_SOURCES:
        raise ConfigError("source must be one of: wavelog, adif_file")
    config['source'] = source

    if source == 'wavelog':
        if not config.get('api_key') or not isinstance(config['api_key'], str):
            raise ConfigError("api_key must be a non-empty string for source=wavelog")

        if not config.get('wavelog_url') or not isinstance(config['wavelog_url'], str):
            raise ConfigError("wavelog_url must be a non-empty string for source=wavelog")

        url = config['wavelog_url'].strip()
        if not url.startswith(('http://', 'https://')):
            raise ConfigError("wavelog_url must start with http:// or https://")
    elif source == 'adif_file':
        adif_file_path = str(config.get('adif_file_path', '')).strip()
        if adif_file_path:
            adif_file = Path(adif_file_path)
            if not adif_file.exists() or not adif_file.is_file():
                raise ConfigError(f"adif_file_path does not exist or is not a file: {adif_file_path}")
            config['adif_file_path'] = str(adif_file)
    
    if not isinstance(config.get('qrz_username'), str):
        raise ConfigError("qrz_username must be a string")
    
    if not isinstance(config.get('qrz_password'), str):
        raise ConfigError("qrz_password must be a string")

    ignored_dxcc = config.get('ignored_dxcc', [])
    if ignored_dxcc is None:
        ignored_dxcc = []
    if not isinstance(ignored_dxcc, list):
        raise ConfigError("ignored_dxcc must be a list of DXCC IDs")

    normalized_ignored_dxcc = []
    for value in ignored_dxcc:
        try:
            dxcc_id = int(str(value).strip())
        except Exception:
            raise ConfigError(f"ignored_dxcc contains invalid DXCC ID: {value}")
        if dxcc_id <= 0:
            raise ConfigError(f"ignored_dxcc contains invalid DXCC ID: {value}")
        normalized_ignored_dxcc.append(dxcc_id)

    config['ignored_dxcc'] = sorted(set(normalized_ignored_dxcc))
    
    return True
