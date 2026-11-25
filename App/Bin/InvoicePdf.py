import os
from decimal import Decimal, ROUND_HALF_UP
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
SELLER = "DriveLab Europe"
CENT = Decimal("0.01")


def create(invoice, path):
    pdfmetrics.registerFont(TTFont("Dv", FONT))
    pdfmetrics.registerFont(TTFont("DvB", FONT_BOLD))
    normal = ParagraphStyle("N", fontName="Dv", fontSize=10, leading=13)
    bold = ParagraphStyle("B", parent=normal, fontName="DvB")
    title = ParagraphStyle("T", parent=bold, fontSize=18, leading=22)
    currency = invoice.get("currency", "EUR")
    client = invoice.get("client_name") or invoice.get("contact") or "-"
    story = [
        Paragraph(escape(SELLER), bold),
        Spacer(1, 6 * mm),
        Paragraph("Factura " + escape(str(invoice["id"])), title),
        Paragraph(escape(str(invoice.get("created", ""))[:10]), normal),
        Spacer(1, 6 * mm),
        Paragraph("Cliente", bold),
        Paragraph(escape(str(client)), normal),
        Spacer(1, 6 * mm),
    ]
    rows = [["Cant.", "Descripción", "Precio", "Total"]]
    for item in invoice.get("items", []):
        line = (Decimal(item["price"]) * item["qty"]).quantize(CENT, ROUND_HALF_UP)
        rows.append([str(item["qty"]), Paragraph(escape(str(item["name"])), normal), f"{item['price']} {currency}", f"{line} {currency}"])
    rows.append(["", "", "Total", f"{invoice['total']} {currency}"])
    table = Table(rows, colWidths=[18 * mm, 90 * mm, 30 * mm, 32 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "DvB"),
        ("FONTNAME", (0, 1), (-1, -1), "Dv"),
        ("FONTNAME", (2, -1), (-1, -1), "DvB"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.black),
        ("LINEABOVE", (0, -1), (-1, -1), 0.5, colors.black),
    ]))
    story.append(table)
    if invoice.get("note"):
        story += [Spacer(1, 6 * mm), Paragraph(escape(str(invoice["note"])), normal)]
    part = path.with_name(path.name + ".part")
    SimpleDocTemplate(str(part), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=20 * mm, bottomMargin=20 * mm).build(story)
    os.replace(part, path)
