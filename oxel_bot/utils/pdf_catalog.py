import os
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from database import SessionLocal, Product


def generate_pdf_catalog() -> str:
    """Generate an official Oxel Handcrafted Wooden Product Catalog PDF."""
    os.makedirs('data/catalogs', exist_ok=True)
    pdf_path = "data/catalogs/Oxel_Product_Catalog.pdf"

    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=letter,
        rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36
    )
    story = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'CatalogTitle',
        parent=styles['Heading1'],
        fontSize=26,
        leading=30,
        textColor=colors.HexColor('#2C2218'),
        fontName='Helvetica-Bold'
    )

    subtitle_style = ParagraphStyle(
        'CatalogSubtitle',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#776655'),
        fontName='Helvetica'
    )

    prod_name_style = ParagraphStyle(
        'ProdName',
        parent=styles['Normal'],
        fontSize=12,
        leading=15,
        textColor=colors.HexColor('#2C2218'),
        fontName='Helvetica-Bold'
    )

    prod_desc_style = ParagraphStyle(
        'ProdDesc',
        parent=styles['Normal'],
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#444444'),
        fontName='Helvetica'
    )

    price_style = ParagraphStyle(
        'PriceStyle',
        parent=styles['Normal'],
        fontSize=12,
        leading=15,
        textColor=colors.HexColor('#884400'),
        fontName='Helvetica-Bold',
        alignment=2  # Right
    )

    # 1. Header Block
    header_data = [
        [
            Paragraph("<b>O X E L</b><br/><font size=10 color='#776655'>SUSTAINABLE ETHIOPIAN WOODWORK</font>", title_style),
            Paragraph(f"<b>PRODUCT CATALOG & PRICE LIST</b><br/>Updated: {datetime.now().strftime('%b %d, %Y')}<br/>Website: oxel.com", subtitle_style)
        ]
    ]
    header_table = Table(header_data, colWidths=[300, 240])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 12))

    # Divider
    divider = Table([['']], colWidths=[540], rowHeights=[2])
    divider.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#D4A373'))]))
    story.append(divider)
    story.append(Spacer(1, 15))

    # 2. Fetch Products
    db = SessionLocal()
    try:
        products = db.query(Product).filter(Product.in_stock == True).all()

        catalog_rows = [
            [Paragraph('<b>Product Details & Description</b>', prod_name_style), Paragraph('<b>Category</b>', prod_name_style), Paragraph('<b>Price (ETB)</b>', price_style)]
        ]

        for p in products:
            finishes_list = [v.finish_name for v in p.variants if v.is_active] if p.variants else ["Natural Oak", "Dark Walnut", "Midnight Ash"]
            finishes_str = ", ".join(finishes_list)

            desc_text = (
                f"<b>{p.name}</b><br/>"
                f"<font size=8 color='#555555'>{p.description or 'Handcrafted solid wood workspace accessory.'}</font><br/>"
                f"<font size=8 color='#885522'>✨ Finishes: {finishes_str} | Rating: ⭐ {p.avg_rating} ({p.review_count} reviews)</font>"
            )

            catalog_rows.append([
                Paragraph(desc_text, prod_desc_style),
                Paragraph(f"<b>{p.category or 'Accessory'}</b>", prod_desc_style),
                Paragraph(f"<b>{p.price:,} ETB</b>", price_style)
            ])

        table = Table(catalog_rows, colWidths=[320, 110, 110])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F4EADF')),
            ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E0D5C5')),
        ]))
        story.append(table)
    finally:
        db.close()

    story.append(Spacer(1, 25))

    # Footer
    from config import SHOP_NAME, TELEGRAM_CHANNEL
    footer_text = Paragraph(
        f"<center><font color='#887766' size=9>To place orders or inquire about custom laser engraving, message us on Telegram: {TELEGRAM_CHANNEL}<br/>{SHOP_NAME} · Addis Ababa, Ethiopia</font></center>",
        styles['Normal']
    )
    story.append(footer_text)

    doc.build(story)
    return pdf_path
