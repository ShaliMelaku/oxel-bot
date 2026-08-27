import os
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle


def generate_shipping_label(order_data: dict) -> str:
    """
    Generate an official OXEL Package Shipping Label PDF.
    order_data keys: order_number, delivery_code, customer_name, phone, shipping_address, delivery_slot, items, total_price, date
    """
    os.makedirs('data/labels', exist_ok=True)
    pdf_path = f"data/labels/LABEL_{order_data['order_number']}.pdf"

    # Standard shipping label size canvas on letter page (4x6 layout proportion)
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=(4 * inch, 6 * inch),
        rightMargin=12, leftMargin=12, topMargin=12, bottomMargin=12
    )
    story = []
    styles = getSampleStyleSheet()

    # Custom styles tailored for shipping labels
    header_style = ParagraphStyle(
        'LabelHeader',
        parent=styles['Normal'],
        fontSize=14,
        leading=16,
        textColor=colors.HexColor('#FFFFFF'),
        fontName='Helvetica-Bold',
        alignment=1 # Center
    )

    subheader_style = ParagraphStyle(
        'LabelSubHeader',
        parent=styles['Normal'],
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#EEEEEE'),
        fontName='Helvetica',
        alignment=1
    )

    section_title = ParagraphStyle(
        'SectionTitle',
        parent=styles['Normal'],
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#666666'),
        fontName='Helvetica-Bold'
    )

    content_bold = ParagraphStyle(
        'ContentBold',
        parent=styles['Normal'],
        fontSize=10,
        leading=13,
        textColor=colors.HexColor('#111111'),
        fontName='Helvetica-Bold'
    )

    content_regular = ParagraphStyle(
        'ContentRegular',
        parent=styles['Normal'],
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#222222'),
        fontName='Helvetica'
    )

    code_box_style = ParagraphStyle(
        'CodeBox',
        parent=styles['Normal'],
        fontSize=16,
        leading=18,
        textColor=colors.HexColor('#990000'),
        fontName='Helvetica-Bold',
        alignment=1
    )

    # 1. Header Block (Oxel Branding)
    header_content = [
        [Paragraph("<b>O X E L  C R A F T</b>", header_style)],
        [Paragraph("EXPEDITED COURIER SHIPPING LABEL", subheader_style)]
    ]
    header_table = Table(header_content, colWidths=[3.6 * inch])
    header_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#2C2218')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 6))

    # 2. Tracking & Order # Box
    order_num = order_data.get('order_number', 'N/A')
    ship_date = order_data.get('date', datetime.now().strftime('%b %d, %Y'))
    slot = order_data.get('delivery_slot', 'Standard')
    shipping_fee = order_data.get('shipping_fee', 0)
    delivery_note = f" (Incl. {shipping_fee:,} ETB Delivery)" if shipping_fee else ""

    track_data = [
        [Paragraph(f"<b>ORDER #:</b> {order_num}", content_bold), Paragraph(f"<b>DATE:</b> {ship_date}", content_regular)],
        [Paragraph(f"<b>SLOT:</b> {slot}", content_regular), Paragraph(f"<b>TOTAL:</b> {order_data.get('total_price', 0):,} ETB{delivery_note}", content_bold)]
    ]
    track_table = Table(track_data, colWidths=[1.8 * inch, 1.8 * inch])
    track_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(track_table)
    story.append(Spacer(1, 6))

    # 3. Ship To Customer Address Box
    cust_name = order_data.get('customer_name', 'Valued Customer')
    cust_phone = order_data.get('phone', 'N/A')
    address = order_data.get('shipping_address', 'Addis Ababa, Ethiopia')

    ship_to_html = f"""
<b>SHIP TO:</b><br/>
<font size=11 color="#000000"><b>{cust_name}</b></font><br/>
<font size=9 color="#333333">📞 <b>{cust_phone}</b></font><br/>
<font size=9 color="#222222">📍 {address}</font>
"""
    ship_to_table = Table([[Paragraph(ship_to_html, content_regular)]], colWidths=[3.6 * inch])
    ship_to_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8F9FA')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#2C2218')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(ship_to_table)
    story.append(Spacer(1, 6))

    # 4. Item Manifest Summary
    items = order_data.get('items', [])
    manifest_rows = [
        [Paragraph("<b>Item Description & Variant</b>", section_title), Paragraph("<b>Qty</b>", section_title)]
    ]
    for it in items:
        p_name = it.get('name', 'Product')
        finish = it.get('finish', 'Standard')
        qty = it.get('quantity', 1)
        engrave = f" (Engrave: '{it.get('engraving')}')" if it.get('engraving') else ""
        item_str = f"<b>{p_name}</b> — {finish}{engrave}"
        manifest_rows.append([Paragraph(item_str, content_regular), Paragraph(str(qty), content_bold)])

    manifest_table = Table(manifest_rows, colWidths=[3.0 * inch, 0.6 * inch])
    manifest_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#EAEAEA')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#DDDDDD')),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(manifest_table)
    story.append(Spacer(1, 6))

    # 5. Security Handoff Instructions (No raw PIN printed on label for security)
    code_html = """
<font size=8 color="#555555"><b>SECURITY HAND-OFF PROCEDURE:</b></font><br/>
<font size=7 color="#777777">Courier must request discrete verification code from customer upon arrival.<br/>
Verify code via Admin Bot to confirm hand-off.</font>
"""
    code_table = Table([[Paragraph(code_html, ParagraphStyle('CodeCenter', parent=styles['Normal'], alignment=1))]], colWidths=[3.6 * inch])
    code_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8F9FA')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#CCCCCC')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(code_table)
    story.append(Spacer(1, 6))

    # 6. Courier Instructions Footer
    footer_p = Paragraph(
        "<center><font size=7 color='#666666'>OXEL LOGISTICS · Delivery courier must verify customer code via Admin Bot.<br/>Return if code fails verification.</font></center>",
        content_regular
    )
    story.append(footer_p)

    doc.build(story)
    return pdf_path
