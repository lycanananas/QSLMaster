import logging
import time
from typing import List, Dict, Optional, Tuple, Callable
from collections import defaultdict

import requests

from .callsign_utils import extract_homecall

try:
    from lxml import html as lxml_html
except Exception:
    lxml_html = None


logger = logging.getLogger(__name__)


def _parse_pzk_response(content: bytes) -> Optional[Tuple[str, str]]:
    if lxml_html is None:
        return None
    tree = lxml_html.fromstring(content)
    status_nodes = tree.xpath("/html/body/table/tr[4]/td/table[2]/tr/td/table/td[2]/table[2]/tr[4]/td[2]")
    ot_nodes = tree.xpath("/html/body/table/tr[4]/td/table[2]/tr/td/table/td[2]/table[2]/tr[5]/td[2]")
    status_text = status_nodes[0].text_content().strip() if status_nodes else ""
    ot_text = ot_nodes[0].text_content().strip() if ot_nodes else ""
    if not status_text and not ot_text:
        return None
    return status_text, ot_text


def _fetch_pzk_member_info(homecall: str) -> Optional[Tuple[str, str]]:
    post_data = {
        "ec_view_members_znak_pokaz": homecall,
        "ec_view_members_action": "view_selected_members",
        "Submit": "Poka%BF",
    }
    t_start = time.perf_counter()
    response = requests.post(
        "https://pzk.org.pl/osec_ec_members_view.php",
        data=post_data,
        timeout=20,
    )
    t_http = time.perf_counter()
    http_time = (t_http - t_start) * 1000
    
    if response.status_code != 200:
        return None
    
    result = _parse_pzk_response(response.content)
    t_end = time.perf_counter()
    parse_time = (t_end - t_http) * 1000
    total_time = (t_end - t_start) * 1000
    
    logger.debug(f"PZK lookup {homecall}: total={total_time:.1f}ms (HTTP={http_time:.1f}ms, parse={parse_time:.1f}ms)")
    
    return result


def process_qsos_poland(qsos: List, log_callback: Optional[Callable[[str, str], None]] = None, progress_callback: Optional[Callable[[int, int], None]] = None) -> Tuple[List, int]:
    def log(level: str, msg: str) -> None:
        if log_callback:
            log_callback(level, msg)
        else:
            getattr(logger, level.lower(), logger.info)(msg)
    
    def progress(current: int, total: int) -> None:
        if progress_callback:
            progress_callback(current, total)
    
    log('INFO', f"Processing {len(qsos)} Poland QSOs")
    results = []
    
    qsos_by_call: Dict[str, List] = defaultdict(list)
    for qso in qsos:
        fullcall = str(qso.get("CALL", "")).strip()
        if fullcall:
            qsos_by_call[fullcall].append(qso)
    
    unique_calls = len(qsos_by_call)
    log('INFO', f"  Unique callsigns to check: {unique_calls}")
    
    pzk_cache: Dict[str, Optional[Tuple[str, str]]] = {}
    
    checked_count = 0
    processed_qsos = 0
    for fullcall, call_qsos in qsos_by_call.items():
        checked_count += 1
        if checked_count % 10 == 0:
            log('INFO', f"  Progress: {checked_count}/{unique_calls} callsigns checked")
        
        t_call_start = time.perf_counter()
        try:
            if fullcall not in pzk_cache:
                homecall = extract_homecall(fullcall)
                
                t_api_start = time.perf_counter()
                info = _fetch_pzk_member_info(homecall)
                t_api_end = time.perf_counter()
                api_time = (t_api_end - t_api_start) * 1000
                
                pzk_cache[fullcall] = info
                
                t_call_end = time.perf_counter()
                total_time = (t_call_end - t_call_start) * 1000
                logger.debug(f"  {fullcall} ({homecall}): total={total_time:.1f}ms (API={api_time:.1f}ms)")
            else:
                info = pzk_cache[fullcall]
            
            if not info:
                log('INFO', f"  PZK result: {fullcall} is not a member of PZK - {len(call_qsos)} QSO(s)")
                continue
            
            status_text, ot_text = info
            is_member = "Jest" in status_text
            via_text = ""
            if ot_text:
                via_text = ot_text.split()[0]
                if via_text.upper().startswith("OT"):
                    via_text = via_text[2:].strip(".- ")
            
            if is_member:
                if via_text:
                    log('INFO', f"  PZK result: {fullcall} is a member of PZK via OT-{via_text} - {len(call_qsos)} QSO(s)")
                else:
                    log('INFO', f"  PZK result: {fullcall} is a member of PZK - {len(call_qsos)} QSO(s)")
                
                if via_text:
                    for qso in call_qsos:
                        qso_copy = dict(qso)
                        qso_copy["QSL_VIA"] = f"OT-{via_text}"
                        qso_copy["QSL_SENT"] = "Y"
                        qso_copy["QSL_SENT_VIA"] = "B"
                        results.append(qso_copy)
                        processed_qsos += 1
                        progress(processed_qsos, len(qsos))
                else:
                    for qso in call_qsos:
                        qso_copy = dict(qso)
                        qso_copy["QSL_SENT"] = "Y"
                        qso_copy["QSL_SENT_VIA"] = "B"
                        results.append(qso_copy)
                        processed_qsos += 1
                        progress(processed_qsos, len(qsos))
            else:
                log('INFO', f"  PZK result: {fullcall} is not a member of PZK - {len(call_qsos)} QSO(s)")
                for _ in call_qsos:
                    processed_qsos += 1
                    progress(processed_qsos, len(qsos))
        except Exception as e:
            log('WARNING', f"  PZK result: {fullcall} lookup error: {e}")
            for _ in call_qsos:
                processed_qsos += 1
                progress(processed_qsos, len(qsos))
    
    return results, len(qsos)
