"""
PDF generation for Account Statement. No Streamlit dependency.
"""
import math
import pandas as pd
from io import BytesIO
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch

try:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    pdfmetrics.registerFont(TTFont('Times-Roman', 'times.ttf'))
    pdfmetrics.registerFont(TTFont('Times-Bold', 'timesbd.ttf'))
    _font_name, _font_bold = 'Times-Roman', 'Times-Bold'
except Exception:
    _font_name, _font_bold = 'Helvetica', 'Helvetica-Bold'


def create_pdf_report(account_info: dict, account_data: pd.DataFrame, from_date: str = None, to_date: str = None) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=50, leftMargin=50, topMargin=50, bottomMargin=50)
    font_name, font_bold = _font_name, _font_bold

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontName=font_bold, fontSize=16, spaceAfter=20, alignment=1)
    normal_style = ParagraphStyle('Normal', parent=styles['Normal'], fontName=font_name, fontSize=14, spaceAfter=6)
    time_style = ParagraphStyle('TimeGenerated', parent=styles['Normal'], fontName=font_name, fontSize=14, spaceAfter=10, alignment=1)
    date_range_style = ParagraphStyle('DateRange', parent=styles['Normal'], fontName=font_name, fontSize=14, spaceAfter=15, alignment=1)
    # Style for description column with text wrapping
    desc_style = ParagraphStyle('Description', parent=styles['Normal'], fontName=font_name, fontSize=8, leading=10, alignment=0)  # alignment=0 is LEFT

    story = []
    story.append(Paragraph("SAO KÊ TÀI KHOẢN/ ACCOUNT STATEMENT", title_style))
    story.append(Spacer(1, 10))
    story.append(Paragraph(f"Thời gian xuất/ Time generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}", time_style))
    story.append(Spacer(1, 10))
    from_date_str = from_date or 'All time'
    to_date_str = to_date or 'Present'
    story.append(Paragraph(f"Từ ngày/ From: {from_date_str} &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; Đến ngày/ To: {to_date_str}", date_range_style))
    story.append(Spacer(1, 15))

    account_info_data = [
        [f"Số tài khoản/ Account Number: {account_info.get('account_number','N/A')}", f"Loại tiền/ Currency: {account_info.get('currency_code','VND')}"],
        [f"Tên tài khoản/ Account Name: {account_info.get('account_name','N/A')}", f"CIF Number: {account_info.get('cif_number','N/A')}"],
        [f"Địa chỉ/ Address: {account_info.get('customer_address','N/A')}", ""],
    ]
    tbl = Table(account_info_data, colWidths=[4*inch, 4*inch])
    tbl.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, -1), 'LEFT'), ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, -1), font_name), ('FONTSIZE', (0, 0), (-1, -1), 14),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4), ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 15))

    if not account_data.empty:
        currency_symbol = "₫" if account_info.get('currency_code', 'VND') == 'VND' else "$"
        transaction_data = [['Ngày GD\n(Transaction Date)', 'Mã giao dịch\n(Reference No.)', 'Số tài khoản truy vấn\n(Account Number)', 'Tên tài khoản truy vấn\n(Account Name)', 'Ngày mở tài khoản\n(Opening Date)', 'Phát sinh có\n(Credit Amount)', 'Phát sinh nợ\n(Debit Amount)', 'Số dư\n(Balance)', 'Diễn giải\n(Description)']]
        def _amt(v):
            try:
                x = float(v) if v is not None else 0
                return f"{currency_symbol}{x:,.0f}" if not math.isnan(x) and x > 0 else ""
            except Exception:
                return ""

        def _bal(v):
            try:
                x = float(v) if v is not None else 0
                return f"{currency_symbol}{x:,.0f}" if not math.isnan(x) else ""
            except Exception:
                return ""

        for _, row in account_data.iterrows():
            dien_giai = str(row.get('Diễn giải', '') or '')
            # Use Paragraph for description to enable text wrapping
            desc_para = Paragraph(dien_giai.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'), desc_style)
            transaction_data.append([
                str(row.get('Ngày GD', '')),
                str(row.get('Mã giao dịch', '')),
                str(row.get('Số tài khoản truy vấn', '')),
                str(row.get('Tên tài khoản truy vấn', '')),
                str(row.get('Ngày mở tài khoản', '')),
                _amt(row.get('Phát sinh có')),
                _amt(row.get('Phát sinh nợ')),
                _bal(row.get('Số dư')),
                desc_para,  # Use Paragraph instead of string for text wrapping
            ])
        trans_tbl = Table(transaction_data, colWidths=[1*inch, 1.2*inch, 1*inch, 1.2*inch, 1*inch, 1*inch, 1*inch, 1*inch, 2*inch])
        trans_tbl.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'), 
            ('ALIGN', (8, 1), (8, -1), 'LEFT'),  # Left align description column (column 8)
            ('FONTNAME', (0, 0), (-1, 0), font_bold), ('FONTNAME', (0, 1), (-1, -1), font_name),
            ('FONTSIZE', (0, 0), (-1, 0), 8), ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6), ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
            ('TOPPADDING', (0, 1), (-1, -1), 4),  # Add top padding for wrapped text
            ('GRID', (0, 0), (-1, -1), 1, colors.black), 
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),  # Top align for wrapped text
        ]))
        story.append(trans_tbl)
    else:
        story.append(Paragraph("No transaction data available for the selected period.", normal_style))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
