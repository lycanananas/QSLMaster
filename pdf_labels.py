import logging
from typing import List, Dict
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, inch
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle

logger = logging.getLogger(__name__)

AVERY_70X25 = {
    'page_width': 210,
    'page_height': 297,
    'label_width': 70,
    'label_height': 25.4,
    'columns': 3,
    'rows': 11,
    'left_margin': 0,
    'top_margin': 4.5,
    'column_gap': 0,
    'row_gap': 0,
}

LABEL_PADDING = 2 * mm
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


def draw_label(c: canvas.Canvas, qso: Dict, x: float, y: float, width: float, height: float, debug_mode: bool = False):
    callsign = qso.get('CALL', 'N/A')
    via = qso.get('QSL_VIA', '').strip()
    date = format_date(qso.get('QSO_DATE', ''))
    time = format_time(qso.get('TIME_ON', ''))
    rst_sent = qso.get('RST_SENT', '')
    mode = qso.get('MODE', '')
    submode = qso.get('SUBMODE', '')
    band = qso.get('BAND', '')
    
    display_mode = submode if submode else mode
    
    x_start = x + LABEL_PADDING
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
    
    if debug_mode:
        c.setStrokeColor(colors.red)
        c.setLineWidth(LINE_WIDTH)
        c.rect(x, y - height, width, height)


def generate_pdf_labels(qsos: List[Dict], output_path: str, debug_mode: bool = False):
    if not qsos:
        logger.warning("No QSOs to generate labels for")
        return
    
    logger.info(f"Generating PDF labels for {len(qsos)} QSOs")
    
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
    total_pages = (len(qsos) + labels_per_page - 1) // labels_per_page
    
    logger.info(f"Creating {total_pages} page(s) with {labels_per_page} labels per page")
    
    qso_index = 0
    
    for page_num in range(total_pages):
        for row in range(specs['rows']):
            for col in range(specs['columns']):
                if qso_index >= len(qsos):
                    break
                
                x = left_margin + col * (label_width + column_gap)
                y = page_height - top_margin - row * (label_height + row_gap)
                
                draw_label(c, qsos[qso_index], x, y, label_width, label_height, debug_mode)
                
                qso_index += 1
            
            if qso_index >= len(qsos):
                break
        
        if qso_index < len(qsos):
            c.showPage()
    
    c.save()
    logger.info(f"PDF labels saved to: {output_path}")


def preview_label_data(qsos: List[Dict], limit: int = 3):
    logger.info(f"Preview of first {min(limit, len(qsos))} labels:")
    
    for i, qso in enumerate(qsos[:limit]):
        callsign = qso.get('CALL', 'N/A')
        via = qso.get('QSL_VIA', '').strip()
        date = format_date(qso.get('QSO_DATE', ''))
        time = format_time(qso.get('TIME_ON', ''))
        rst = qso.get('RST_SENT', '')
        mode = qso.get('SUBMODE') or qso.get('MODE', '')
        band = qso.get('BAND', '')
        
        logger.info(f"\n  Label {i+1}:")
        logger.info(f"    To Radio: {callsign}")
        if via:
            logger.info(f"    Via: {via}")
        logger.info(f"    Date: {date}, Time: {time}")
        logger.info(f"    RST: {rst}, Mode: {mode}, Band: {band}")
