import os
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle


def generate_pdf_invoice(order_data: dict) -> str:
    """
    Generate an official OXEL PDF Invoice.
    order_data keys: order_number, customer_name, phone, address, items, total_amount, discount, payment_method, date
    """
    os.makedirs('data/invoices', exist_ok=True)
    pdf_path = f"data/invoices/INVOICE_{order_data['order_number']}.pdf"

    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=letter,
        rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40
    )
    story = []
    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'InvoiceTitle',
        parent=styles['Heading1'],
        fontSize=24,
        leading=28,
        textColor=colors.HexColor('#2C2218'),
        fontName='Helvetica-Bold'
    )
    subtitle_style = ParagraphStyle(
        'InvoiceSubtitle',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#665544'),
        fontName='Helvetica'
    )
    bold_style = ParagraphStyle(
        'BoldText',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        fontName='Helvetica-Bold'
    )

    # Header Table
    header_data = [
        [
            Paragraph("<b>O X E L</b><br/><font size=10 color='#776655'>TOOLS FOR THE DIGITAL CRAFT</font>", title_style),
            Paragraph(f"<b>OFFICIAL INVOICE</b><br/>Invoice #: <b>{order_data['order_number']}</b><br/>Date: {order_data.get('date', datetime.now().strftime('%b %d, %Y'))}", subtitle_style)
        ]
    ]
    header_table = Table(header_data, colWidths=[300, 230])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 15))

    # Divider line
    divider = Table([['']], colWidths=[530], rowHeights=[2])
    divider.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#D4A373'))]))
    story.append(divider)
    story.append(Spacer(1, 15))

    # Customer & Store Info Table
    cust_info = f"""<b>BILLED TO:</b><br/>
Name: {order_data.get('customer_name', 'Valued Customer')}<br/>
Phone: {order_data.get('phone', 'N/A')}<br/>
Address: {order_data.get('address', 'N/A')}
"""
    from config import SHOP_NAME, SHOP_WEBSITE, TELEGRAM_CHANNEL
    store_info = f"""<b>ISSUED BY:</b><br/>
{SHOP_NAME}<br/>
Addis Ababa, Ethiopia<br/>
Telegram: {TELEGRAM_CHANNEL}
"""
    info_table = Table([[Paragraph(cust_info, styles['Normal']), Paragraph(store_info, styles['Normal'])]], colWidths=[265, 265])
    info_table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    story.append(info_table)
    story.append(Spacer(1, 20))

    # Items Table Header
    items_table_data = [
        [Paragraph('<b>Item Description & Finish</b>', bold_style), Paragraph('<b>Qty</b>', bold_style), Paragraph('<b>Unit Price</b>', bold_style), Paragraph('<b>Subtotal</b>', bold_style)]
    ]

    for item in order_data.get('items', []):
        name = item.get('name', 'Product')
        finish = item.get('finish', 'Standard')
        engraving = f"<br/><font color='#885522'>+ Custom Laser Engraving: '{item.get('engraving')}'</font>" if item.get('engraving') else ""
        qty = item.get('quantity', 1)
        price = item.get('price', 0)
        subtotal = item.get('subtotal', price * qty)

        desc_p = Paragraph(f"<b>{name}</b><br/><font color='#555555'>Finish: {finish}</font>{engraving}", styles['Normal'])
        items_table_data.append([
            desc_p,
            Paragraph(str(qty), styles['Normal']),
            Paragraph(f"{price:,} ETB", styles['Normal']),
            Paragraph(f"{subtotal:,} ETB", styles['Normal'])
        ])

    items_table = Table(items_table_data, colWidths=[260, 50, 110, 110])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F4EADF')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#2C2218')),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E0D5C5')),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 15))

    # Totals Summary
    tot_amt = order_data.get('total_amount', 0)
    disc = order_data.get('discount', 0)
    pay_method = order_data.get('payment_method', 'TELEBIRR/CBE')

    totals_data = [
        ['', Paragraph('<b>Subtotal:</b>', styles['Normal']), Paragraph(f"{tot_amt + disc:,} ETB", styles['Normal'])],
        ['', Paragraph('<b>Discount:</b>', styles['Normal']), Paragraph(f"-{disc:,} ETB", styles['Normal']) if disc > 0 else Paragraph("0 ETB", styles['Normal'])],
        ['', Paragraph('<b>Total Paid:</b>', bold_style), Paragraph(f"<b>{tot_amt:,} ETB</b>", bold_style)],
        ['', Paragraph('<b>Payment Status:</b>', styles['Normal']), Paragraph("<font color='green'><b>VERIFIED & CONFIRMED</b></font>", styles['Normal'])],
        ['', Paragraph('<b>Payment Method:</b>', styles['Normal']), Paragraph(f"<b>{pay_method.upper()}</b>", styles['Normal'])]
    ]

    totals_table = Table(totals_data, colWidths=[260, 140, 130])
    totals_table.setStyle(TableStyle([
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(totals_table)
    story.append(Spacer(1, 25))

    from config import SHOP_NAME, TELEGRAM_CHANNEL
    footer_text = Paragraph(
        f"<center><font color='#887766' size=9>Thank you for supporting sustainable Ethiopian craft! <br/>For inquiries, contact us on Telegram: {TELEGRAM_CHANNEL}</font></center>",
        styles['Normal']
    )
    story.append(footer_text)

    doc.build(story)
    return pdf_path
