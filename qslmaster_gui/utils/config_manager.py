import json
import logging
import uuid
from pathlib import Path
from typing import Dict, Any, Optional, List

from . import keyring_handler


logger = logging.getLogger(__name__)

PNG_MAGIC = b'\x89PNG\r\n\x1a\n'
JPG_MAGIC = (b'\xff\xd8\xff', b'\xff\xd9')


def _get_logos_dir() -> Path:
    logos_dir = get_config_dir() / 'logos'
    logos_dir.mkdir(parents=True, exist_ok=True)
    return logos_dir


def _validate_logo_file(file_path: str) -> bool:
    path = Path(file_path)
    
    if not path.exists() or not path.is_file():
        return False
    
    ext = path.suffix.lower()
    if ext not in ('.png', '.jpg', '.jpeg'):
        logger.warning(f"Invalid logo extension: {ext}")
        return False
    
    try:
        with open(path, 'rb') as f:
            magic = f.read(8)
    except Exception as e:
        logger.warning(f"Failed to read logo file: {e}")
        return False
    
    if magic.startswith(PNG_MAGIC):
        return True
    
    if magic.startswith(JPG_MAGIC[0]):
        try:
            with open(path, 'rb') as f:
                f.seek(-2, 2)
                if f.read() == JPG_MAGIC[1]:
                    return True
        except Exception:
            pass
    
    logger.warning("Logo file is not a valid PNG or JPG")
    return False


def _get_logo_path_for_config(config_id: str) -> Path:
    return _get_logos_dir() / f"{config_id}.png"


def _save_logo_file(config_id: str, source_file: str) -> bool:
    logger.info(f"_save_logo_file called with source: {source_file}, config_id: {config_id}")
    
    if not source_file or not source_file.strip():
        logger.error("Logo file path is empty")
        return False
    
    if not _validate_logo_file(source_file):
        logger.error(f"Logo file validation failed for {source_file}")
        return False
    
    try:
        source_path = Path(source_file)
        dest_path = _get_logo_path_for_config(config_id)
        
        logger.info(f"Copying logo from {source_path} to {dest_path}")
        logger.info(f"Source exists: {source_path.exists()}, size: {source_path.stat().st_size if source_path.exists() else 'N/A'}")
        
        with open(source_path, 'rb') as f_src:
            content = f_src.read()
            logger.info(f"Read {len(content)} bytes from source")
            with open(dest_path, 'wb') as f_dst:
                f_dst.write(content)
        
        logger.info(f"Destination file size: {dest_path.stat().st_size}")
        dest_path.chmod(0o600)
        logger.info(f"Logo saved for config {config_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to save logo: {e}", exc_info=True)
        return False


def _delete_logo_file(config_id: str) -> bool:
    logo_path = _get_logo_path_for_config(config_id)
    if logo_path.exists():
        try:
            logo_path.unlink()
            logger.info(f"Logo deleted for config {config_id}")
            return True
        except Exception as e:
            logger.warning(f"Failed to delete logo: {e}")
            return True
    return True


def get_logo_path(config_id: str) -> Optional[str]:
    logo_path = _get_logo_path_for_config(config_id)
    if logo_path.exists():
        return str(logo_path)
    return None


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


def _load_configs_metadata() -> Dict[str, Any]:
    config_file = get_config_file()
    
    metadata = {
        'configs': [],
        'current_config_id': None
    }
    
    if config_file.exists():
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict) and 'configs' in data:
                    metadata = data
                    logger.info(f"Loaded configs metadata from {config_file}")
        except Exception as e:
            logger.warning(f"Failed to load configs metadata: {e}")
    
    return metadata


def _save_configs_metadata(metadata: Dict[str, Any]) -> bool:
    config_file = get_config_file()
    
    try:
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)
        config_file.chmod(0o600)
        logger.info(f"Saved configs metadata to {config_file}")
        return True
    except Exception as e:
        logger.error(f"Failed to save configs metadata: {e}")
        return False


def list_all_configs() -> List[Dict[str, Any]]:
    metadata = _load_configs_metadata()
    return metadata.get('configs', [])


def get_current_config_id() -> Optional[str]:
    metadata = _load_configs_metadata()
    return metadata.get('current_config_id')


def set_current_config_id(config_id: str) -> bool:
    metadata = _load_configs_metadata()
    metadata['current_config_id'] = config_id
    return _save_configs_metadata(metadata)


def create_config(name: str, wavelog_url: str, qrz_username: str, api_key: str, qrz_password: Optional[str] = None) -> Optional[str]:
    config_id = str(uuid.uuid4())
    
    metadata = _load_configs_metadata()
    
    config_entry = {
        'id': config_id,
        'name': name,
        'wavelog_url': wavelog_url,
        'qrz_username': qrz_username
    }
    
    metadata['configs'].append(config_entry)
    if not metadata['current_config_id']:
        metadata['current_config_id'] = config_id
    
    if _save_configs_metadata(metadata):
        if not keyring_handler.store_credential(f'qslmaster_config_{config_id}_api_key', api_key):
            logger.warning(f"Failed to store API key for config {config_id}")
        
        if qrz_password:
            if not keyring_handler.store_credential(f'qslmaster_config_{config_id}_qrz_password', qrz_password):
                logger.warning(f"Failed to store QRZ password for config {config_id}")
        
        return config_id
    
    return None


def get_config(config_id: str) -> Optional[Dict[str, Any]]:
    metadata = _load_configs_metadata()
    
    config_entry = None
    for cfg in metadata.get('configs', []):
        if cfg['id'] == config_id:
            config_entry = cfg
            break
    
    if not config_entry:
        return None
    
    config = config_entry.copy()
    
    api_key = keyring_handler.get_credential(f'qslmaster_config_{config_id}_api_key')
    if api_key:
        config['api_key'] = api_key
    
    qrz_password = keyring_handler.get_credential(f'qslmaster_config_{config_id}_qrz_password')
    if qrz_password:
        config['qrz_password'] = qrz_password
    
    logo_path = get_logo_path(config_id)
    if logo_path:
        config['logo_path'] = logo_path
    
    return config


def update_config(config_id: str, name: str, wavelog_url: str, qrz_username: str, api_key: str, qrz_password: Optional[str] = None) -> bool:
    metadata = _load_configs_metadata()
    
    for cfg in metadata.get('configs', []):
        if cfg['id'] == config_id:
            cfg['name'] = name
            cfg['wavelog_url'] = wavelog_url
            cfg['qrz_username'] = qrz_username
            break
    else:
        return False
    
    if _save_configs_metadata(metadata):
        if not keyring_handler.store_credential(f'qslmaster_config_{config_id}_api_key', api_key):
            logger.warning(f"Failed to update API key for config {config_id}")
        
        if qrz_password:
            if not keyring_handler.store_credential(f'qslmaster_config_{config_id}_qrz_password', qrz_password):
                logger.warning(f"Failed to update QRZ password for config {config_id}")
        
        return True
    
    return False


def delete_config(config_id: str) -> bool:
    metadata = _load_configs_metadata()
    
    metadata['configs'] = [cfg for cfg in metadata.get('configs', []) if cfg['id'] != config_id]
    
    if metadata['current_config_id'] == config_id:
        metadata['current_config_id'] = metadata['configs'][0]['id'] if metadata['configs'] else None
    
    if _save_configs_metadata(metadata):
        keyring_handler.delete_credential(f'qslmaster_config_{config_id}_api_key')
        keyring_handler.delete_credential(f'qslmaster_config_{config_id}_qrz_password')
        _delete_logo_file(config_id)
        return True
    
    return False

