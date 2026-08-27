import os
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from database import SessionLocal, Order, Product, User, Payment, LoyaltyTransaction


def generate_pdf_sales_report() -> str:
    """Generate an official Oxel Financial & Sales Summary PDF Report."""
    os.makedirs('data/reports', exist_ok=True)
    report_date = datetime.now().strftime('%Y_%m_%d')
    pdf_path = f"data/reports/Oxel_Sales_Report_{report_date}.pdf"

    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=letter,
        rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36
    )
    story = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'ReportTitle',
        parent=styles['Heading1'],
        fontSize=24,
        leading=28,
        textColor=colors.HexColor('#2C2218'),
        fontName='Helvetica-Bold'
    )

    subtitle_style = ParagraphStyle(
        'ReportSubtitle',
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

    metric_val_style = ParagraphStyle(
        'MetricVal',
        parent=styles['Normal'],
        fontSize=14,
        leading=16,
        textColor=colors.HexColor('#2C2218'),
        fontName='Helvetica-Bold',
        alignment=1  # Center
    )

    metric_lbl_style = ParagraphStyle(
        'MetricLbl',
        parent=styles['Normal'],
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#776655'),
        fontName='Helvetica',
        alignment=1
    )

    # 1. Header
    header_data = [
        [
            Paragraph("<b>O X E L</b><br/><font size=10 color='#776655'>MANAGEMENT EXECUTIVE REPORT</font>", title_style),
            Paragraph(f"<b>FINANCIAL & SALES REPORT</b><br/>Generated: {datetime.now().strftime('%b %d, %Y · %I:%M %p')}", subtitle_style)
        ]
    ]
    header_table = Table(header_data, colWidths=[300, 240])
    header_table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    story.append(header_table)
    story.append(Spacer(1, 12))

    # Divider
    divider = Table([['']], colWidths=[540], rowHeights=[2])
    divider.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#D4A373'))]))
    story.append(divider)
    story.append(Spacer(1, 15))

    db = SessionLocal()
    try:
        all_orders = db.query(Order).all()
        verified_orders = [o for o in all_orders if o.status in ['verified', 'confirmed', 'shipped', 'delivered']]
        total_revenue = sum(o.total_price for o in verified_orders)
        total_customers = db.query(User).count()
        total_products = db.query(Product).count()

        # 2. Key Metrics Summary Grid
        kpi_data = [
            [
                Paragraph(f"<b>{total_revenue:,} ETB</b>", metric_val_style),
                Paragraph(f"<b>{len(verified_orders)}</b>", metric_val_style),
                Paragraph(f"<b>{len(all_orders)}</b>", metric_val_style),
                Paragraph(f"<b>{total_customers}</b>", metric_val_style)
            ],
            [
                Paragraph("TOTAL REVENUE", metric_lbl_style),
                Paragraph("PAID ORDERS", metric_lbl_style),
                Paragraph("TOTAL ORDERS", metric_lbl_style),
                Paragraph("REGISTERED USERS", metric_lbl_style)
            ]
        ]

        kpi_table = Table(kpi_data, colWidths=[135, 135, 135, 135])
        kpi_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8F4EE')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E0D5C5')),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ]))
        story.append(kpi_table)
        story.append(Spacer(1, 20))

        # 3. Recent Orders Breakdown Table
        story.append(Paragraph("<b>REVENUE & ORDER BREAKDOWN (RECENT ORDERS)</b>", bold_style))
        story.append(Spacer(1, 6))

        order_rows = [
            [Paragraph('<b>Order #</b>', bold_style), Paragraph('<b>Customer</b>', bold_style), Paragraph('<b>Status</b>', bold_style), Paragraph('<b>Amount</b>', bold_style)]
        ]

        recent_orders = db.query(Order).order_by(Order.created_at.desc()).limit(12).all()
        for o in recent_orders:
            cust = db.query(User).filter(User.user_id == o.user_id).first()
            cname = f"{cust.first_name or ''} {cust.last_name or ''}".strip() if cust else "Customer"
            order_rows.append([
                Paragraph(f"<code>{o.order_number}</code>", styles['Normal']),
                Paragraph(cname, styles['Normal']),
                Paragraph(o.status.upper(), styles['Normal']),
                Paragraph(f"<b>{o.total_price:,} ETB</b>", styles['Normal'])
            ])

        orders_table = Table(order_rows, colWidths=[130, 180, 110, 120])
        orders_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#EAE0D5')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#DDDDDD')),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(orders_table)

    finally:
        db.close()

    story.append(Spacer(1, 25))

    footer_text = Paragraph(
        f"<center><font color='#887766' size=9>CONFIDENTIAL — FOR INTERNAL OXEL MANAGEMENT USE ONLY</font></center>",
        styles['Normal']
    )
    story.append(footer_text)

    doc.build(story)
    return pdf_path
