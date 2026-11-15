import time
import requests
from typing import Dict, Any, Optional, Tuple, List
from qslmaster_version import get_user_agent


class WavelogAPIError(Exception):
    pass


class WavelogAuthError(WavelogAPIError):
    pass


def _raise_v1_http_error(response: requests.Response) -> None:
    reason = ''
    try:
        payload = response.json()
        if isinstance(payload, dict):
            reason = str(payload.get('reason') or '')
    except ValueError:
        pass
    if response.status_code in (401, 403):
        raise WavelogAuthError(
            f"Wavelog API key rejected ({reason or f'HTTP {response.status_code}'}). "
            f"Check the API key and its permissions"
        )
    raise WavelogAPIError(f"HTTP error {response.status_code}: {reason}" if reason else f"HTTP error {response.status_code}")


def _strip_adif_header(adif_content: str) -> str:
    eoh_pos = adif_content.upper().find('<EOH>')
    if eoh_pos != -1:
        adif_content = adif_content[eoh_pos + 5:]
    return adif_content.strip()


class WavelogAPI:

    api_version = 'v1'
    supports_date_filter = False

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': get_user_agent()
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

            if response.status_code >= 400:
                _raise_v1_http_error(response)
            return response.json()
        except requests.exceptions.ConnectionError as e:
            raise WavelogAPIError(f"Connection error: {e}")
        except requests.exceptions.Timeout:
            raise WavelogAPIError("Request timeout")
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
            if response.status_code >= 400:
                _raise_v1_http_error(response)
            result = response.json()
            if not isinstance(result, list):
                raise WavelogAPIError("Expected list of stations from api/station_info")
            return result
        except requests.exceptions.ConnectionError as e:
            raise WavelogAPIError(f"Connection error: {e}")
        except requests.exceptions.Timeout:
            raise WavelogAPIError("Request timeout")
        except requests.exceptions.RequestException as e:
            raise WavelogAPIError(f"Request failed: {e}")
        except ValueError as e:
            raise WavelogAPIError(f"Invalid JSON response: {e}")

    def can_mark_as_sent(self) -> bool:
        return False

    def test_access(self) -> Dict[str, Any]:
        version_data = self.get_version()
        stations = self.get_station_info()
        if stations:
            self._make_request('get_contacts_adif', {'station_id': str(stations[0].get('station_id', '')), 'fetchfromid': 2147483647}, timeout=30)
        return {
            'api': self.api_version,
            'version': version_data.get('version', 'N/A'),
            'stations': len(stations),
            'can_mark_as_sent': False,
        }

    def get_contacts_adif_for_station(self, station_id: str) -> Tuple[str, int]:
        response = self._make_request('get_contacts_adif', {'station_id': station_id, 'fetchfromid': 0}, timeout=30)
        qso_count = int(response.get('exported_qsos', 0) or 0)
        adif_content = response.get('adif', '') or ''
        return adif_content, qso_count

    def get_contacts_adif(self, station_ids: Optional[List[str]] = None, qso_since: Optional[str] = None, qso_until: Optional[str] = None) -> Tuple[str, int]:
        if not station_ids:
            station_ids = [str(station.get('station_id', '')) for station in self.get_station_info()]
            station_ids = [station_id for station_id in station_ids if station_id]
            if not station_ids:
                raise WavelogAPIError("No stations found in Wavelog")

        all_qso_records = []
        total_qso_count = 0

        for station_id in station_ids:
            adif_content, qso_count = self.get_contacts_adif_for_station(str(station_id))
            if qso_count > 0 and adif_content:
                all_qso_records.append(_strip_adif_header(adif_content))
                total_qso_count += qso_count

        return '\n'.join(all_qso_records), total_qso_count


WAVELOG_API_V2_TOKEN_PREFIX = 'wl2_'
WAVELOG_API_V2_REQUIRED_SCOPES = ('qso:read', 'station:read')
WAVELOG_API_V2_MARK_AS_SENT_SCOPE = 'qso:write'
WAVELOG_API_V2_PAGE_SIZE = 5000
WAVELOG_API_V2_MAX_RETRIES = 5
WAVELOG_API_V2_MAX_RETRY_WAIT_SECONDS = 60


def is_wavelog_api_v2_key(api_key: str) -> bool:
    return str(api_key or '').strip().startswith(WAVELOG_API_V2_TOKEN_PREFIX)


def create_wavelog_api(base_url: str, api_key: str):
    if is_wavelog_api_v2_key(api_key):
        return WavelogAPIv2(base_url, api_key)
    return WavelogAPI(base_url, api_key)


class WavelogAPIv2:

    api_version = 'v2'
    supports_date_filter = True

    def __init__(self, base_url: str, api_key: str, sleep=time.sleep):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key.strip()
        self.sleep = sleep
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': get_user_agent(),
            'Authorization': f'Bearer {self.api_key}',
            'Accept': 'application/json',
        })
        self.token_info: Dict[str, Any] = {}

        self._check_token()

    def _build_api_url(self, resource: str) -> str:
        resource = resource.strip('/')
        if self.base_url.endswith('/api/v2'):
            return f"{self.base_url}/{resource}"
        if self.base_url.endswith('/api'):
            return f"{self.base_url}/v2/{resource}"
        return f"{self.base_url}/api/v2/{resource}"

    @staticmethod
    def _parse_error(response: requests.Response) -> Tuple[str, str, Dict[str, Any]]:
        try:
            error = response.json().get('error', {})
        except (ValueError, AttributeError):
            error = {}
        if not isinstance(error, dict):
            error = {}
        details = error.get('details') if isinstance(error.get('details'), dict) else {}
        return str(error.get('code') or ''), str(error.get('message') or ''), details

    @classmethod
    def _raise_http_error(cls, response: requests.Response) -> None:
        code, message, details = cls._parse_error(response)

        if code == 'insufficient_scope':
            required_scope = details.get('required_scope', '')
            raise WavelogAuthError(f"Wavelog API v2 token is missing required scope: {required_scope or message}")
        if code == 'token_expired':
            raise WavelogAuthError("Wavelog API v2 token has expired. Create a new token in Wavelog")
        if code in ('unauthorized', 'invalid_token'):
            raise WavelogAuthError("Wavelog API v2 token is invalid or revoked. Check the token in Wavelog")
        if response.status_code in (401, 403):
            raise WavelogAuthError(f"Wavelog API v2 access denied ({code or f'HTTP {response.status_code}'}): {message}".strip())
        if code:
            raise WavelogAPIError(f"HTTP error {response.status_code} ({code}): {message}".strip())
        raise WavelogAPIError(f"HTTP error {response.status_code}")

    def _get_retry_wait(self, response: requests.Response) -> float:
        _, _, details = self._parse_error(response)
        for value in (details.get('retry_after'), response.headers.get('Retry-After')):
            try:
                if value is not None:
                    return max(1.0, min(float(value), WAVELOG_API_V2_MAX_RETRY_WAIT_SECONDS))
            except (TypeError, ValueError):
                continue
        return 5.0

    def _request(self, method: str, resource: str, params: Optional[Dict[str, Any]] = None, json_body: Optional[Dict[str, Any]] = None, timeout: int = 10) -> Dict[str, Any]:
        url = self._build_api_url(resource)

        for attempt in range(WAVELOG_API_V2_MAX_RETRIES + 1):
            try:
                response = self.session.request(method, url, params=params or None, json=json_body, timeout=timeout)
            except requests.exceptions.ConnectionError as e:
                raise WavelogAPIError(f"Connection error: {e}")
            except requests.exceptions.Timeout:
                raise WavelogAPIError("Request timeout")
            except requests.exceptions.RequestException as e:
                raise WavelogAPIError(f"Request failed: {e}")

            if response.status_code == 429 and attempt < WAVELOG_API_V2_MAX_RETRIES:
                self.sleep(self._get_retry_wait(response))
                continue
            break

        if response.status_code == 429:
            raise WavelogAPIError("Wavelog API v2 rate limit exceeded. Try again later")
        if response.status_code == 404 and resource in ('token', 'status'):
            raise WavelogAPIError("Wavelog API v2 not found. Wavelog 3.1.0 or later is required for wl2_ tokens")
        if response.status_code >= 400:
            self._raise_http_error(response)

        try:
            result = response.json()
        except ValueError as e:
            raise WavelogAPIError(f"Invalid JSON response: {e}")
        if not isinstance(result, dict) or 'data' not in result:
            raise WavelogAPIError(f"Unexpected API v2 response from {resource}")
        return result

    def _make_request(self, resource: str, params: Optional[Dict[str, Any]] = None, timeout: int = 10) -> Dict[str, Any]:
        return self._request('GET', resource, params=params, timeout=timeout)

    def _check_token(self) -> None:
        self.token_info = self._make_request('token').get('data') or {}
        missing = [scope for scope in WAVELOG_API_V2_REQUIRED_SCOPES if scope not in self.get_scopes()]
        if missing:
            raise WavelogAuthError(f"Wavelog API v2 token is missing required scope(s): {', '.join(missing)}")

    def get_scopes(self) -> List[str]:
        return list(self.token_info.get('scopes') or [])

    def can_mark_as_sent(self) -> bool:
        return WAVELOG_API_V2_MARK_AS_SENT_SCOPE in self.get_scopes()

    def get_version(self) -> Dict[str, Any]:
        return {
            'version': 'API v2 (3.1.0 or later)',
            'owner': self.token_info.get('owner', ''),
            'scopes': self.get_scopes(),
            'expires_at': self.token_info.get('expires_at'),
        }

    def test_access(self) -> Dict[str, Any]:
        stations = self.get_station_info()
        self._make_request('qso', {'limit': 1})
        return {
            'api': self.api_version,
            'version': 'API v2 (3.1.0 or later)',
            'owner': self.token_info.get('owner', ''),
            'scopes': self.get_scopes(),
            'expires_at': self.token_info.get('expires_at'),
            'stations': len(stations),
            'can_mark_as_sent': self.can_mark_as_sent(),
        }

    def get_station_info(self) -> list:
        stations = self._make_request('station').get('data')
        if not isinstance(stations, list):
            raise WavelogAPIError("Expected list of stations from api/v2/station")
        return [
            {
                'station_id': str(station.get('id', '')),
                'station_callsign': str(station.get('callsign', '') or ''),
                'station_profile_name': str(station.get('name', '') or ''),
                'station_active': '1' if station.get('active') in (True, 1, '1', 'true') else '0',
            }
            for station in stations
            if isinstance(station, dict)
        ]

    @staticmethod
    def _build_qso_filters(station_ids: Optional[List[str]], qso_since: Optional[str], qso_until: Optional[str]) -> Dict[str, Any]:
        filters: Dict[str, Any] = {}
        if station_ids:
            filters['station_id'] = ','.join(str(station_id) for station_id in station_ids)
        if qso_since:
            filters['qso_since'] = qso_since
        if qso_until:
            filters['qso_until'] = qso_until
        return filters

    def get_contacts_adif(self, station_ids: Optional[List[str]] = None, qso_since: Optional[str] = None, qso_until: Optional[str] = None) -> Tuple[str, int]:
        filters = self._build_qso_filters(station_ids, qso_since, qso_until)
        qso_records = []
        total_qso_count = 0
        page = 1

        while True:
            response = self._make_request('qso', {
                **filters,
                'format': 'adif',
                'per_page': WAVELOG_API_V2_PAGE_SIZE,
                'page': page,
            }, timeout=60)
            data = response.get('data') or {}
            meta = response.get('meta') or {}

            qso_count = int(data.get('exported') or 0)
            adif_content = data.get('adif') or ''
            if qso_count > 0 and adif_content:
                qso_records.append(_strip_adif_header(adif_content))
                total_qso_count += qso_count

            if not meta.get('has_more'):
                break
            page += 1

        return '\n'.join(qso_records), total_qso_count

    def list_qsos(self, station_ids: Optional[List[str]] = None, qso_since: Optional[str] = None, qso_until: Optional[str] = None) -> List[Dict[str, Any]]:
        filters = self._build_qso_filters(station_ids, qso_since, qso_until)
        qsos: List[Dict[str, Any]] = []
        page = 1

        while True:
            response = self._make_request('qso', {
                **filters,
                'per_page': WAVELOG_API_V2_PAGE_SIZE,
                'page': page,
            }, timeout=60)
            data = response.get('data') or []
            if not isinstance(data, list):
                raise WavelogAPIError("Expected list of QSOs from api/v2/qso")
            qsos.extend(item for item in data if isinstance(item, dict))

            if not (response.get('meta') or {}).get('has_more'):
                break
            page += 1

        return qsos

    def update_qso(self, qso_id: int, fields: Dict[str, Any]) -> Dict[str, Any]:
        return self._request('PATCH', f'qso/{int(qso_id)}', json_body=fields, timeout=30).get('data') or {}
