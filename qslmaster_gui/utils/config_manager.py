"""
Configuration manager for GUI
Handles secure storage and retrieval of settings
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from . import keyring_handler


logger = logging.getLogger(__name__)


def get_config_dir() -> Path:
    if Path.home().name == 'root':
        config_home = Path('/root/.config')
    else:
        config_home = Path.home() / '.config'
    
    config_dir = config_home / 'qslmaster'
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_config_file() -> Path:
    return get_config_dir() / 'config.json'


def load_gui_config() -> Dict[str, Any]:
    config_file = get_config_file()
    project_config_file = Path(__file__).parent.parent.parent / 'config.json'
    
    default_config = {
        'wavelog_url': '',
        'qrz_username': '',
        'api_key_in_keyring': keyring_handler.is_keyring_available(),
        'auto_generate_pdf': False,
        'last_from_date': '',
        'last_to_date': '',
    }
    
    if config_file.exists():
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                file_config = json.load(f)
                default_config.update(file_config)
                logger.info(f"Loaded configuration from {config_file}")
        except Exception as e:
            logger.warning(f"Failed to load configuration: {e}")
    
    if not default_config.get('api_key') and project_config_file.exists():
        try:
            with open(project_config_file, 'r', encoding='utf-8') as f:
                project_config = json.load(f)
                if project_config.get('api_key'):
                    default_config['api_key'] = project_config['api_key']
                if project_config.get('wavelog_url') and not default_config.get('wavelog_url'):
                    default_config['wavelog_url'] = project_config['wavelog_url']
                if project_config.get('qrz_username') and not default_config.get('qrz_username'):
                    default_config['qrz_username'] = project_config['qrz_username']
                if project_config.get('qrz_password'):
                    default_config['qrz_password'] = project_config['qrz_password']
                logger.info(f"Loaded configuration from {project_config_file}")
        except Exception as e:
            logger.warning(f"Failed to load project configuration: {e}")
    
    if default_config.get('api_key_in_keyring'):
        api_key = keyring_handler.get_api_key()
        if api_key:
            default_config['api_key'] = api_key
        
        qrz_password = keyring_handler.get_qrz_password()
        if qrz_password:
            default_config['qrz_password'] = qrz_password
    
    return default_config


def save_gui_config(config: Dict[str, Any]) -> bool:
    config_file = get_config_file()
    
    config_to_save = {
        k: v for k, v in config.items()
        if k not in ['api_key', 'qrz_password']
    }
    
    try:
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config_to_save, f, indent=2)
        
        config_file.chmod(0o600)
        logger.info(f"Configuration saved to {config_file}")
        return True
    except Exception as e:
        logger.error(f"Failed to save configuration: {e}")
        return False


def save_credentials(api_key: Optional[str], qrz_password: Optional[str]) -> bool:
    success = True
    
    if api_key:
        if not keyring_handler.store_api_key(api_key):
            success = False
    
    if qrz_password:
        if not keyring_handler.store_qrz_password(qrz_password):
            success = False
    
    return success


def get_credentials_from_config(config: Dict[str, Any]) -> Dict[str, Any]:
    creds = {}
    
    if 'api_key' in config:
        creds['api_key'] = config['api_key']
    else:
        api_key = keyring_handler.get_api_key()
        if api_key:
            creds['api_key'] = api_key
    
    if 'qrz_password' in config:
        creds['qrz_password'] = config['qrz_password']
    else:
        qrz_password = keyring_handler.get_qrz_password()
        if qrz_password:
            creds['qrz_password'] = qrz_password
    
    creds['wavelog_url'] = config.get('wavelog_url', '')
    creds['qrz_username'] = config.get('qrz_username', '')
    
    return creds
