import requests
from typing import Dict, Any, Optional, Tuple
from urllib.parse import urljoin


class WavelogAPIError(Exception):
    pass


class WavelogAPI:
    
    def __init__(self, base_url: str, api_key: str, station_id: str):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.station_id = station_id
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'QSLMaster/1.0'
        })
    
    def _make_request(self, endpoint: str, data: Optional[Dict[str, Any]] = None, timeout: int = 10) -> Dict[str, Any]:
        url = urljoin(self.base_url, endpoint)
        
        if data is None:
            data = {}
        body = {'key': self.api_key, 'station_id': self.station_id, **data}
        
        try:
            response = self.session.post(url, json=body, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.ConnectionError as e:
            raise WavelogAPIError(f"Connection error: {e}")
        except requests.exceptions.Timeout:
            raise WavelogAPIError("Request timeout")
        except requests.exceptions.HTTPError as e:
            raise WavelogAPIError(f"HTTP error {response.status_code}: {e}")
        except requests.exceptions.RequestException as e:
            raise WavelogAPIError(f"Request failed: {e}")
        except ValueError as e:
            raise WavelogAPIError(f"Invalid JSON response: {e}")
    
    def get_version(self) -> Dict[str, Any]:
        return self._make_request('api/version')
    
    def get_contacts_adif(self) -> Tuple[str, int]:
        response = self._make_request('api/get_contacts_adif', {'fetchfromid': 0}, timeout=30)
        
        qso_count = response.get('exported_qsos', 0)
        
        if qso_count == 0:
            raise WavelogAPIError("No QSOs found in Wavelog")
        
        adif_content = response.get('adif', '')
        return adif_content, qso_count
