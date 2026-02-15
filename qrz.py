import requests
import xml.etree.ElementTree as ET
from typing import Dict, Any, Optional


class QRZAPIError(Exception):
    pass


class QRZAPI:
    
    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self.base_url = 'https://xmldata.qrz.com/xml/current/'
        self.session_key = None
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'QSLMaster/1.0'
        })
    
    def _get_session_key(self) -> str:
        try:
            response = self.session.get(
                self.base_url,
                params={'username': self.username, 'password': self.password},
                timeout=10
            )
            response.raise_for_status()
            root = ET.fromstring(response.content)
            
            ns = {'qrz': 'http://xmldata.qrz.com'}
            session_elem = root.find('.//qrz:Session/qrz:Key', ns)
            
            if session_elem is None or session_elem.text is None:
                raise QRZAPIError("Failed to obtain session key from QRZ")
            return session_elem.text
        except requests.exceptions.RequestException as e:
            raise QRZAPIError(f"QRZ login failed: {e}")
        except ET.ParseError as e:
            raise QRZAPIError(f"QRZ response parse error: {e}")
    
    def _ensure_session(self) -> None:
        if not self.session_key:
            self.session_key = self._get_session_key()
    
    def lookup_call(self, callsign: str) -> Dict[str, Any]:
        self._ensure_session()
        try:
            response = self.session.get(
                self.base_url,
                params={'s': self.session_key, 'callsign': callsign},
                timeout=10
            )
            response.raise_for_status()
            root = ET.fromstring(response.content)
            
            ns = {'qrz': 'http://xmldata.qrz.com'}
            callsign_elem = root.find('.//qrz:Callsign', ns)
            
            if callsign_elem is None:
                return {}
            
            data = {}
            for child in callsign_elem:
                tag = child.tag
                if '}' in tag:
                    tag = tag.split('}', 1)[1]
                tag = tag.lower()
                text = child.text or ''
                data[tag] = text
            
            return data
        except requests.exceptions.RequestException as e:
            raise QRZAPIError(f"QRZ lookup failed: {e}")
        except ET.ParseError as e:
            raise QRZAPIError(f"QRZ response parse error: {e}")
    
    def has_qsl_manager(self, callsign: str = '', data: Optional[Dict[str, Any]] = None) -> bool:
        try:
            if data is None:
                data = self.lookup_call(callsign)
            
            qslmgr = data.get('qslmgr', '').lower()
            
            if not qslmgr:
                return False
            
            valid_methods = [
                'biuro', 'bureau', 'bureua', 'bireau', 'bureao', 'buiro', 'biro',
                'buro', 'büro', 'agence', 'direct'
            ]
            return any(method in qslmgr for method in valid_methods)
        except QRZAPIError:
            return False
