import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


def get_cache_dir() -> Path:
    cache_dir = Path(os.environ.get('QSLMASTER_CACHE_DIR') or Path.home() / '.cache' / 'qslmaster')
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def read_cache_metadata(metadata_file: Path) -> Dict[str, Any]:
    try:
        with open(metadata_file, 'r', encoding='utf-8') as file_handle:
            metadata = json.load(file_handle)
        return metadata if isinstance(metadata, dict) else {}
    except (OSError, ValueError):
        return {}


def write_cache_metadata(metadata_file: Path, url: str, **extra: Any) -> None:
    metadata = {
        'downloaded_at': datetime.now().isoformat(),
        'url': url,
        **extra,
    }
    with open(metadata_file, 'w', encoding='utf-8') as file_handle:
        json.dump(metadata, file_handle, indent=2)


def get_cache_age_days(metadata: Dict[str, Any]) -> Optional[int]:
    try:
        downloaded_at = datetime.fromisoformat(str(metadata['downloaded_at']))
    except (KeyError, ValueError):
        return None
    return (datetime.now() - downloaded_at).days
