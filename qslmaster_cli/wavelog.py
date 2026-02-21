import requests
from typing import Dict, Any, Optional, Tuple


class WavelogAPIError(Exception):
    pass


class WavelogAPI:
    
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'QSLMaster/1.0'
        })
        
        self._check_version()

    def _build_api_url(self, endpoint: str) -> str:
        endpoint = endpoint.lstrip('/')
        if endpoint.startswith('api/'):
            endpoint = endpoint[4:]

        if self.base_url.endswith('/api'):
            return f"{self.base_url}/{endpoint}"

        return f"{self.base_url}/api/{endpoint}"
    
    def _check_version(self) -> None:
        version_data = self.get_version()
        version_str = version_data.get('version', '0.0.0')
        
        try:
            parts = version_str.split('.')
            major_int = int(parts[0]) if len(parts) > 0 else 0
            
            if major_int < 2:
                raise WavelogAPIError(
                    f"Wavelog version {version_str} is not supported. "
                    f"Minimum required version is 2.0.0"
                )
        except (ValueError, AttributeError, IndexError) as e:
            raise WavelogAPIError(f"Cannot parse Wavelog version '{version_str}': {e}")
    
    def _make_request(self, endpoint: str, data: Optional[Dict[str, Any]] = None, timeout: int = 10, use_get: bool = False) -> Dict[str, Any]:
        url = self._build_api_url(endpoint)
        
        if data is None:
            data = {}
        
        try:
            if use_get:
                params = {'key': self.api_key, **data}
                response = self.session.get(url, params=params, timeout=timeout)
            else:
                body = {'key': self.api_key, **data}
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
        return self._make_request('version')
    
    def get_station_info(self) -> list:
        url = self._build_api_url(f'station_info/{self.api_key}')
        
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            result = response.json()
            if not isinstance(result, list):
                raise WavelogAPIError("Expected list of stations from api/station_info")
            return result
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
    
    def get_contacts_adif_for_station(self, station_id: str) -> Tuple[str, int]:
        response = self._make_request('get_contacts_adif', {'station_id': station_id, 'fetchfromid': 0}, timeout=30)
        qso_count = response.get('exported_qsos', 0)
        adif_content = response.get('adif', '')
        return adif_content, qso_count
    
    def get_contacts_adif(self, station_id: Optional[str] = None) -> Tuple[str, int]:
        if station_id:
            adif_content, qso_count = self.get_contacts_adif_for_station(str(station_id))
            if qso_count == 0:
                raise WavelogAPIError(f"No QSOs found for station_id={station_id}")

            eoh_pos = adif_content.find('<EOH>')
            if eoh_pos != -1:
                adif_content = adif_content[eoh_pos + 5:].strip()
            return adif_content, qso_count

        stations = self.get_station_info()
        
        if not stations:
            raise WavelogAPIError("No stations found in Wavelog")
        
        all_qso_records = []
        total_qso_count = 0
        
        for station in stations:
            station_id = str(station.get('station_id', ''))
            if not station_id:
                continue
            
            try:
                adif_content, qso_count = self.get_contacts_adif_for_station(station_id)
                if qso_count > 0:
                    eoh_pos = adif_content.find('<EOH>')
                    if eoh_pos != -1:
                        qso_data = adif_content[eoh_pos + 5:]
                        all_qso_records.append(qso_data.strip())
                        total_qso_count += qso_count
            except WavelogAPIError:
                continue
        
        if total_qso_count == 0:
            raise WavelogAPIError("No QSOs found in any station")
        
        combined_adif = '\n'.join(all_qso_records)
        return combined_adif, total_qso_count
