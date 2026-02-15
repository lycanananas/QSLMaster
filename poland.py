import logging
from typing import List, Dict, Optional, Tuple

import requests
from pyhamtools.callinfo import Callinfo

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
    response = requests.post(
        "https://pzk.org.pl/osec_ec_members_view.php",
        data=post_data,
        timeout=20,
    )
    if response.status_code != 200:
        return None
    return _parse_pzk_response(response.content)


def process_qsos_poland(qsos: List) -> List[Dict[str, object]]:
    logger.info(f"Processing {len(qsos)} Poland QSOs")
    results = []

    for qso in qsos:
        fullcall = str(qso.get("CALL", "")).strip()
        if not fullcall:
            continue

        try:
            homecall = Callinfo.get_homecall(fullcall)
        except Exception:
            homecall = fullcall

        info = _fetch_pzk_member_info(homecall)
        if not info:
            logger.info(f"  PZK result: {fullcall} ({homecall}) is not a member of PZK")
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
                logger.info(f"  PZK result: {fullcall} ({homecall}) is a member of PZK via OT-{via_text}")
            else:
                logger.info(f"  PZK result: {fullcall} ({homecall}) is a member of PZK")
        else:
            logger.info(f"  PZK result: {fullcall} ({homecall}) is not a member of PZK")
        if is_member and via_text:
            qso_copy = dict(qso)
            qso_copy["QSL_VIA"] = f"OT-{via_text}"
            qso_copy["QSL_SENT"] = "Y"
            results.append(qso_copy)

    return results
