import logging
from typing import List, Dict
from datetime import datetime
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, inch
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle
from reportlab.lib.utils import ImageReader

from .logging_handler import LogHandler

logger = logging.getLogger(__name__)

AVERY_70X25 = {
    'page_width': 210,
    'page_height': 297,
    'label_width': 70,
    'label_height': 25.4,
    'columns': 3,
    'rows': 11,
    'left_margin': 0,
    'top_margin': 9,
    'column_gap': 0,
    'row_gap': 0,
}

LABEL_PADDING = 2 * mm
LABEL_PADDING_LEFT = 3 * mm
LABEL_TOP_OFFSET = 2 * mm
HEADER_FONT_SIZE = 12
DATA_FONT_SIZE = 8
UNDERLINE_OFFSET = 0.5 * mm
LINE_WIDTH = 0.5
SPACING_AFTER_HEADER = 3 * mm
SPACING_AFTER_VIA = 2 * mm
SPACING_NO_VIA = 1 * mm
TOTAL_SEPARATOR_SPACE = 2 * mm
SPACING_BETWEEN_FIELDS = 3 * mm

LOGO_IMAGE_PATH = "logo.png"
LOGO_WIDTH = 15 * mm
LOGO_HEIGHT = 15 * mm
LOGO_RIGHT_MARGIN = 2 * mm
LOGO_TOP_MARGIN = 2 * mm
CONFIRMATION_OFFSET = 1.5 * mm
CONFIRMATION_FONT_SIZE = 6


def format_date(date_str: str) -> str:
    try:
        dt = datetime.strptime(date_str, '%Y%m%d')
        return dt.strftime('%d.%m.%Y')
    except:
        return date_str


def format_time(time_str: str) -> str:
    try:
        if len(time_str) >= 4:
            return f"{time_str[:2]}:{time_str[2:4]}"
        return time_str
    except:
        return time_str


def draw_label(c: canvas.Canvas, qso: Dict, x: float, y: float, width: float, height: float, debug_mode: bool = False, logo_path: str = "logo.png"):
    callsign = qso.get('CALL', 'N/A')
    via = qso.get('QSL_VIA', '').strip()
    date = format_date(qso.get('QSO_DATE', ''))
    time = format_time(qso.get('TIME_ON', ''))
    rst_sent = qso.get('RST_SENT', '')
    mode = qso.get('MODE', '')
    submode = qso.get('SUBMODE', '')
    band = qso.get('BAND', '')
    
    display_mode = submode if submode else mode
    
    x_start = x + LABEL_PADDING + LABEL_PADDING_LEFT
    y_start = y - LABEL_PADDING - LABEL_TOP_OFFSET
    
    current_y = y_start
    
    c.setFont("Helvetica-Bold", HEADER_FONT_SIZE)
    c.drawString(x_start, current_y, "To Radio:")
    c.setFont("Helvetica", HEADER_FONT_SIZE)
    callsign_x = x_start + c.stringWidth("To Radio: ", "Helvetica-Bold", HEADER_FONT_SIZE)
    c.drawString(callsign_x, current_y, callsign)
    callsign_width = c.stringWidth(callsign, "Helvetica", HEADER_FONT_SIZE)
    c.setStrokeColor(colors.black)
    c.setLineWidth(LINE_WIDTH)
    c.line(callsign_x, current_y - UNDERLINE_OFFSET, callsign_x + callsign_width, current_y - UNDERLINE_OFFSET)
    current_y -= SPACING_AFTER_HEADER
    
    via_y = current_y
    
    if via:
        c.setFont("Helvetica-Bold", DATA_FONT_SIZE)
        c.drawString(x_start, current_y, "Via:")
        c.setFont("Helvetica", DATA_FONT_SIZE)
        via_x = x_start + c.stringWidth("Via: ", "Helvetica-Bold", DATA_FONT_SIZE)
        c.drawString(via_x, current_y, via)
        via_width = c.stringWidth(via, "Helvetica", DATA_FONT_SIZE)
        c.setStrokeColor(colors.black)
        c.setLineWidth(LINE_WIDTH)
        c.line(via_x, current_y - UNDERLINE_OFFSET, via_x + via_width, current_y - UNDERLINE_OFFSET)
        current_y -= SPACING_AFTER_VIA
    else:
        current_y = via_y - SPACING_AFTER_VIA
    
    current_y -= TOTAL_SEPARATOR_SPACE
    
    c.setFont("Helvetica-Bold", DATA_FONT_SIZE)
    c.drawString(x_start, current_y, "Date:")
    c.setFont("Helvetica", DATA_FONT_SIZE)
    date_x = x_start + c.stringWidth("Date: ", "Helvetica-Bold", DATA_FONT_SIZE)
    c.drawString(date_x, current_y, date)
    current_y -= SPACING_BETWEEN_FIELDS
    
    c.setFont("Helvetica-Bold", DATA_FONT_SIZE)
    c.drawString(x_start, current_y, "Time:")
    c.setFont("Helvetica", DATA_FONT_SIZE)
    time_x = x_start + c.stringWidth("Time: ", "Helvetica-Bold", DATA_FONT_SIZE)
    c.drawString(time_x, current_y, f"{time} UTC")
    current_y -= SPACING_BETWEEN_FIELDS
    
    c.setFont("Helvetica-Bold", DATA_FONT_SIZE)
    c.drawString(x_start, current_y, "RST:")
    c.setFont("Helvetica", DATA_FONT_SIZE)
    rst_x = x_start + c.stringWidth("RST: ", "Helvetica-Bold", DATA_FONT_SIZE)
    c.drawString(rst_x, current_y, rst_sent)
    current_y -= SPACING_BETWEEN_FIELDS
    
    c.setFont("Helvetica-Bold", DATA_FONT_SIZE)
    c.drawString(x_start, current_y, "Mode:")
    c.setFont("Helvetica", DATA_FONT_SIZE)
    mode_x = x_start + c.stringWidth("Mode: ", "Helvetica-Bold", DATA_FONT_SIZE)
    c.drawString(mode_x, current_y, display_mode)
    current_y -= SPACING_BETWEEN_FIELDS
    
    if band:
        c.setFont("Helvetica-Bold", DATA_FONT_SIZE)
        c.drawString(x_start, current_y, "Band:")
        c.setFont("Helvetica", DATA_FONT_SIZE)
        band_x = x_start + c.stringWidth("Band: ", "Helvetica-Bold", DATA_FONT_SIZE)
        c.drawString(band_x, current_y, band)
    
    logo_x = x + width - LABEL_PADDING - LOGO_WIDTH - LOGO_RIGHT_MARGIN
    logo_y = y - LABEL_PADDING - 1 * mm - LOGO_HEIGHT
    
    resolved_logo_path = Path(logo_path)
    if not resolved_logo_path.is_absolute():
        resolved_logo_path = Path(__file__).parent / logo_path
    
    if resolved_logo_path.exists():
        try:
            img = ImageReader(str(resolved_logo_path))
            c.drawImage(img, logo_x, logo_y, width=LOGO_WIDTH, height=LOGO_HEIGHT, mask='auto')
        except Exception as e:
            LogHandler.get_instance().log('WARNING', f"Failed to load logo image: {e}")
    
    logo_center_x = logo_x + LOGO_WIDTH / 2
    confirmation_x = logo_center_x
    confirmation_y = logo_y - CONFIRMATION_OFFSET - 3 * mm
    c.setFont("Helvetica-Bold", CONFIRMATION_FONT_SIZE)
    c.setFillColor(colors.black)
    c.drawCentredString(confirmation_x, confirmation_y + CONFIRMATION_FONT_SIZE, "Confirming")
    c.drawCentredString(confirmation_x, confirmation_y, "2-way QSO")

    if debug_mode:
        c.setStrokeColor(colors.red)
        c.setLineWidth(LINE_WIDTH)
        c.rect(x, y - height, width, height)


def get_labels_per_page() -> int:
    return int(AVERY_70X25['columns']) * int(AVERY_70X25['rows'])


def normalize_pdf_page_spec(page_spec, labels_per_page: int) -> Dict:
    if isinstance(page_spec, dict):
        offset_raw = page_spec.get('offset', 0)
        skip_raw = page_spec.get('skip_slots', [])
    else:
        text = str(page_spec or '').strip()
        if not text:
            return {'offset': 0, 'skip_slots': []}
        if '|' in text:
            offset_part, skip_part = text.split('|', 1)
        elif ';' in text:
            offset_part, skip_part = text.split(';', 1)
        else:
            offset_part, skip_part = text, ''
        offset_raw = offset_part.strip() or '0'
        skip_raw = [value.strip() for value in skip_part.split(',')] if skip_part.strip() else []

    offset = int(str(offset_raw).strip() or '0')
    if offset < 0 or offset > labels_per_page:
        raise ValueError(f'PDF page offset must be between 0 and {labels_per_page}, got: {offset}')

    skip_slots = []
    seen_slots = set()
    for value in skip_raw:
        text = str(value or '').strip()
        if not text:
            continue
        slot_number = int(text)
        if slot_number < 1 or slot_number > labels_per_page:
            raise ValueError(f'PDF skipped label must be between 1 and {labels_per_page}, got: {slot_number}')
        if slot_number in seen_slots:
            continue
        seen_slots.add(slot_number)
        skip_slots.append(slot_number)

    return {
        'offset': offset,
        'skip_slots': sorted(skip_slots),
    }


def normalize_pdf_page_specs(page_specs) -> List[Dict]:
    if page_specs is None:
        return []

    labels_per_page = get_labels_per_page()
    normalized_specs = []
    for value in page_specs:
        text = str(value or '').strip()
        if not text:
            continue
        normalized_specs.append(normalize_pdf_page_spec(value, labels_per_page))
    return normalized_specs


def normalize_pdf_page_offsets(offsets) -> List[int]:
    if offsets is None:
        return []
    if isinstance(offsets, str):
        raw_values = offsets.split(',')
    else:
        raw_values = offsets
    return [spec['offset'] for spec in normalize_pdf_page_specs(raw_values)]


def calculate_pdf_page_count(qso_count: int, page_specs: List[Dict], labels_per_page: int) -> int:
    remaining = qso_count
    page_count = 0

    while remaining > 0:
        page_spec = page_specs[page_count] if page_count < len(page_specs) else {'offset': 0, 'skip_slots': []}
        blocked_slots = set(page_spec.get('skip_slots', []))
        capacity = 0
        for slot_number in range(page_spec.get('offset', 0) + 1, labels_per_page + 1):
            if slot_number in blocked_slots:
                continue
            capacity += 1
        if capacity <= 0:
            page_count += 1
            continue
        remaining -= capacity
        page_count += 1

    return page_count


def generate_pdf_labels(
    qsos: List[Dict],
    output_path: str,
    debug_mode: bool = False,
    logo_path: str = "logo.png",
    page_specs=None,
):
    if not qsos:
        LogHandler.get_instance().log('WARNING', "No QSOs to generate labels for")
        return
    
    LogHandler.get_instance().log('INFO', f"Generating PDF labels for {len(qsos)} QSOs")
    
    specs = AVERY_70X25
    
    c = canvas.Canvas(output_path, pagesize=A4)
    page_width, page_height = A4
    
    def mm_to_points(mm_val):
        return mm_val * mm
    
    label_width = mm_to_points(specs['label_width'])
    label_height = mm_to_points(specs['label_height'])
    left_margin = mm_to_points(specs['left_margin'])
    top_margin = mm_to_points(specs['top_margin'])
    column_gap = mm_to_points(specs['column_gap'])
    row_gap = mm_to_points(specs['row_gap'])
    
    labels_per_page = specs['columns'] * specs['rows']
    normalized_page_specs = normalize_pdf_page_specs(page_specs)
    total_pages = calculate_pdf_page_count(len(qsos), normalized_page_specs, labels_per_page)
    
    LogHandler.get_instance().log('INFO', f"Creating {total_pages} page(s) with {labels_per_page} labels per page")
    if normalized_page_specs:
        details = []
        for index, page_spec in enumerate(normalized_page_specs, start=1):
            skipped_text = ','.join(str(slot) for slot in page_spec['skip_slots']) or '-'
            details.append(f"page {index}: offset={page_spec['offset']}, skipped={skipped_text}")
        LogHandler.get_instance().log('INFO', f"Using PDF page options: {'; '.join(details)}")
    
    qso_index = 0
    
    for page_num in range(total_pages):
        page_spec = normalized_page_specs[page_num] if page_num < len(normalized_page_specs) else {'offset': 0, 'skip_slots': []}
        blocked_slots = set(page_spec.get('skip_slots', []))
        start_slot = page_spec.get('offset', 0)
        for slot in range(start_slot, labels_per_page):
            if qso_index >= len(qsos):
                break
            if (slot + 1) in blocked_slots:
                continue

            row = slot // specs['columns']
            col = slot % specs['columns']
            x = left_margin + col * (label_width + column_gap)
            y = page_height - top_margin - row * (label_height + row_gap)

            draw_label(c, qsos[qso_index], x, y, label_width, label_height, debug_mode, logo_path)

            qso_index += 1
        
        if qso_index < len(qsos):
            c.showPage()
    
    c.save()
    LogHandler.get_instance().log('INFO', f"PDF labels saved to: {output_path}")


def preview_label_data(qsos: List[Dict], limit: int = 3):
    LogHandler.get_instance().log('INFO', f"Preview of first {min(limit, len(qsos))} labels:")
    
    for i, qso in enumerate(qsos[:limit]):
        callsign = qso.get('CALL', 'N/A')
        via = qso.get('QSL_VIA', '').strip()
        date = format_date(qso.get('QSO_DATE', ''))
        time = format_time(qso.get('TIME_ON', ''))
        rst = qso.get('RST_SENT', '')
        mode = qso.get('SUBMODE') or qso.get('MODE', '')
        band = qso.get('BAND', '')
        
        LogHandler.get_instance().log('INFO', f"\n  Label {i+1}:")
        LogHandler.get_instance().log('INFO', f"    To Radio: {callsign}")
        if via:
            LogHandler.get_instance().log('INFO', f"    Via: {via}")
        LogHandler.get_instance().log('INFO', f"    Date: {date}, Time: {time}")
        LogHandler.get_instance().log('INFO', f"    RST: {rst}, Mode: {mode}, Band: {band}")
