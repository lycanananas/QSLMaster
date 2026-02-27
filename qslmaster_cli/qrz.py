import requests
import xml.etree.ElementTree as ET
import logging
import time
import re
import unicodedata
from typing import Dict, Any, Optional

from .callsign_utils import extract_homecall


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
            'User-Agent': 'QSLMaster/1.2'
        })
        self.logger = logging.getLogger(__name__)
    
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
        callsign = extract_homecall(callsign)
        self._ensure_session()
        try:
            t_http_start = time.perf_counter()
            response = self.session.get(
                self.base_url,
                params={'s': self.session_key, 'callsign': callsign},
                timeout=10
            )
            response.raise_for_status()
            t_http_end = time.perf_counter()
            http_time = (t_http_end - t_http_start) * 1000
            
            t_parse_start = time.perf_counter()
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
            
            t_parse_end = time.perf_counter()
            parse_time = (t_parse_end - t_parse_start) * 1000
            total_time = http_time + parse_time
            
            self.logger.debug(f"QRZ lookup {callsign}: total={total_time:.1f}ms (HTTP={http_time:.1f}ms, parse={parse_time:.1f}ms)")
            
            return data
        except requests.exceptions.RequestException as e:
            raise QRZAPIError(f"QRZ lookup failed: {e}")
        except ET.ParseError as e:
            raise QRZAPIError(f"QRZ response parse error: {e}")
    
    def has_qsl_manager(self, callsign: str = '', data: Optional[Dict[str, Any]] = None) -> bool:
        try:
            if data is None:
                data = self.lookup_call(callsign)
            
            qslmgr_raw = str(data.get('qslmgr', '') or '')
            if not qslmgr_raw.strip():
                return False

            qslmgr = qslmgr_raw.lower().strip()
            qslmgr = qslmgr.replace('w/o', 'without')
            qslmgr = qslmgr.replace('w\\o', 'without')
            qslmgr = re.sub(r"[\[\](){}/\\|;,:]+", " ", qslmgr)
            qslmgr = re.sub(r"\s+", " ", qslmgr).strip()

            qslmgr_folded = unicodedata.normalize('NFKD', qslmgr)
            qslmgr_folded = ''.join(ch for ch in qslmgr_folded if not unicodedata.combining(ch))

            allow_words = r"(?:biuro|agence|biro|buro|burea\w*)"
            deny_words = r"(?:no|not|without|none|brak|bez|kein|ohne|sans)"

            deny_patterns = [
                rf"\b{deny_words}\b(?:\W+\w+){{0,2}}\W+\b{allow_words}\b",
                rf"\bno\s*{allow_words}\b",
                rf"\b{deny_words}\b\W+\bqsl\b(?:\W+\w+){{0,2}}\W+\b{allow_words}\b",
            ]

            for pattern in deny_patterns:
                if re.search(pattern, qslmgr_folded, flags=re.IGNORECASE):
                    return False

            if re.search(rf"\b{allow_words}\b", qslmgr_folded, flags=re.IGNORECASE):
                return True

            return False
        except QRZAPIError:
            return False
