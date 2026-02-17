"""
Keyring handler for secure credential storage
"""
import logging
from typing import Optional

try:
    import keyring
    from keyring.errors import KeyringError
    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False
    KeyringError = Exception


logger = logging.getLogger(__name__)

SERVICE_NAME = "qslmaster"
API_KEY_ID = "wavelog_api_key"
QRZ_PASSWORD_ID = "qrz_password"


def is_keyring_available() -> bool:
    return KEYRING_AVAILABLE


def store_api_key(api_key: str) -> bool:
    if not KEYRING_AVAILABLE:
        logger.warning("Keyring not available, credentials will not be stored securely")
        return False
    
    try:
        keyring.set_password(SERVICE_NAME, API_KEY_ID, api_key)
        logger.info("API key stored in keyring")
        return True
    except KeyringError as e:
        logger.warning(f"Failed to store API key in keyring: {e}")
        return False


def get_api_key() -> Optional[str]:
    if not KEYRING_AVAILABLE:
        return None
    
    try:
        return keyring.get_password(SERVICE_NAME, API_KEY_ID)
    except KeyringError as e:
        logger.warning(f"Failed to retrieve API key from keyring: {e}")
        return None


def store_qrz_password(password: str) -> bool:
    if not KEYRING_AVAILABLE:
        logger.warning("Keyring not available, credentials will not be stored securely")
        return False
    
    try:
        keyring.set_password(SERVICE_NAME, QRZ_PASSWORD_ID, password)
        logger.info("QRZ password stored in keyring")
        return True
    except KeyringError as e:
        logger.warning(f"Failed to store QRZ password in keyring: {e}")
        return False


def get_qrz_password() -> Optional[str]:
    if not KEYRING_AVAILABLE:
        return None
    
    try:
        return keyring.get_password(SERVICE_NAME, QRZ_PASSWORD_ID)
    except KeyringError as e:
        logger.warning(f"Failed to retrieve QRZ password from keyring: {e}")
        return None


def clear_credentials() -> None:
    if not KEYRING_AVAILABLE:
        return
    
    try:
        try:
            keyring.delete_password(SERVICE_NAME, API_KEY_ID)
        except KeyringError:
            pass
        
        try:
            keyring.delete_password(SERVICE_NAME, QRZ_PASSWORD_ID)
        except KeyringError:
            pass
        
        logger.info("Credentials cleared from keyring")
    except Exception as e:
        logger.warning(f"Error clearing credentials: {e}")
