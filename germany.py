import logging
from typing import List


logger = logging.getLogger(__name__)


def process_qsos_germany(qsos: List) -> None:
    logger.info(f"Processing {len(qsos)} Germany QSOs")
