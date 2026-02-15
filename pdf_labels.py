"""
PDF Label Generator for QSL Cards
Supports Avery 5160 format (30 labels per page, 3 columns × 10 rows)
"""

import logging
from typing import List, Dict
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import mm, inch
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle

logger = logging.getLogger(__name__)

AVERY_5160 = {
    'page_width': 215.9,
    'page_height': 279.4,
    'label_width': 66.675,
    'label_height': 25.4,
    'columns': 3,
    'rows': 10,
    'left_margin': 4.7625,
    'top_margin': 12.7,
    'column_gap': 3.175,
    'row_gap': 0,
}


def format_date(date_str: str) -> str:
    """Convert YYYYMMDD to readable format"""
    try:
        dt = datetime.strptime(date_str, '%Y%m%d')
        return dt.strftime('%d %b %Y')
    except:
        return date_str


def format_time(time_str: str) -> str:
    """Convert HHMMSS to HH:MM"""
    try:
        if len(time_str) >= 4:
            return f"{time_str[:2]}:{time_str[2:4]}"
        return time_str
    except:
        return time_str


def draw_label(c: canvas.Canvas, qso: Dict, x: float, y: float, width: float, height: float):
    """Draw a single QSL label at the specified position"""
    
    callsign = qso.get('CALL', 'N/A')
    via = qso.get('QSL_VIA', '').strip()
    date = format_date(qso.get('QSO_DATE', ''))
    time = format_time(qso.get('TIME_ON', ''))
    rst_sent = qso.get('RST_SENT', '')
    mode = qso.get('MODE', '')
    submode = qso.get('SUBMODE', '')
    band = qso.get('BAND', '')
    
    display_mode = submode if submode else mode
    
    padding = 2 * mm
    x_start = x + padding
    y_start = y - padding
    
    header_size = 9
    data_size = 7
    label_size = 6
    
    current_y = y_start
    
    c.setFont("Helvetica-Bold", header_size)
    c.drawString(x_start, current_y, f"To Radio: {callsign}")
    current_y -= 3 * mm
    
    if via:
        c.setFont("Helvetica", data_size)
        c.drawString(x_start, current_y, f"Via: {via}")
        current_y -= 3.5 * mm
    else:
        current_y -= 1 * mm
    
    c.setStrokeColor(colors.grey)
    c.setLineWidth(0.5)
    c.line(x_start, current_y, x + width - padding, current_y)
    current_y -= 1.5 * mm
    
    c.setFont("Helvetica", data_size)
    
    c.drawString(x_start, current_y, f"Date: {date}")
    current_y -= 2.5 * mm
    c.drawString(x_start, current_y, f"Time: {time} UTC")
    current_y -= 2.5 * mm
    
    c.drawString(x_start, current_y, f"RST: {rst_sent}")
    c.drawString(x_start + 15 * mm, current_y, f"Mode: {display_mode}")
    if band:
        c.drawString(x_start + 35 * mm, current_y, f"Band: {band}")


def generate_pdf_labels(qsos: List[Dict], output_path: str, config: Dict = None):
    """
    Generate PDF with QSL labels in Avery 5160 format
    
    Args:
        qsos: List of QSO dictionaries
        output_path: Path to save the PDF file
        config: Optional configuration dictionary
    """
    
    if not qsos:
        logger.warning("No QSOs to generate labels for")
        return
    
    logger.info(f"Generating PDF labels for {len(qsos)} QSOs")
    
    specs = AVERY_5160
    
    c = canvas.Canvas(output_path, pagesize=letter)
    page_width, page_height = letter
    
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
                
                draw_label(c, qsos[qso_index], x, y, label_width, label_height)
                
                qso_index += 1
            
            if qso_index >= len(qsos):
                break
        
        if qso_index < len(qsos):
            c.showPage()
    
    c.save()
    logger.info(f"PDF labels saved to: {output_path}")


def preview_label_data(qsos: List[Dict], limit: int = 3):
    """
    Preview what will be printed on labels (for debugging)
    """
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
