import json
import sys
from pathlib import Path
from typing import Dict, Any


class ConfigError(Exception):
    pass


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
    
    required_fields = ['api_key', 'station_id', 'wavelog_url']
    optional_fields = ['qrz_username', 'qrz_password']
    
    missing_fields = [field for field in required_fields if field not in config]
    if missing_fields:
        raise ConfigError(f"Missing required configuration fields: {', '.join(missing_fields)}")
    
    for field in optional_fields:
        if field not in config:
            config[field] = ''
    
    return config


def validate_config(config: Dict[str, Any]) -> bool:
    if not config.get('api_key') or not isinstance(config['api_key'], str):
        raise ConfigError("api_key must be a non-empty string")
    
    if not config.get('station_id') or not isinstance(config['station_id'], str):
        raise ConfigError("station_id must be a non-empty string")
    
    if not config.get('wavelog_url') or not isinstance(config['wavelog_url'], str):
        raise ConfigError("wavelog_url must be a non-empty string")
    
    url = config['wavelog_url'].strip()
    if not url.startswith(('http://', 'https://')):
        raise ConfigError("wavelog_url must start with http:// or https://")
    
    if not isinstance(config.get('qrz_username'), str):
        raise ConfigError("qrz_username must be a string")
    
    if not isinstance(config.get('qrz_password'), str):
        raise ConfigError("qrz_password must be a string")
    
    return True
