import logging
from typing import List


logger = logging.getLogger(__name__)


def process_qsos_poland(qsos: List) -> None:
    logger.info(f"Processing {len(qsos)} Poland QSOs")
