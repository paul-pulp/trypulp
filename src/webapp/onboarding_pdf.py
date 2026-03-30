"""
Onboarding PDF — POS export instructions for new cafe owners.
Attached to the first magic link email only.
"""

import tempfile
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER


# Brand colors
WARM_800 = HexColor("#6c5041")
WARM_600 = HexColor("#9c7b60")
WARM_200 = HexColor("#e6dbd0")
TERRA_600 = HexColor("#b35e39")
SAGE_600 = HexColor("#5a7d60")


def _build_styles():
    """Create branded paragraph styles."""
    base = getSampleStyleSheet()

    styles = {
        "title": ParagraphStyle(
            "title",
            parent=base["Title"],
            fontSize=22,
            textColor=WARM_800,
            spaceAfter=6,
        ),
        "subtitle": ParagraphStyle(
            "subtitle",
            parent=base["Normal"],
            fontSize=12,
            textColor=WARM_600,
            spaceAfter=20,
            alignment=TA_CENTER,
        ),
        "heading": ParagraphStyle(
            "heading",
            parent=base["Heading2"],
            fontSize=14,
            textColor=TERRA_600,
            spaceBefore=16,
            spaceAfter=8,
        ),
        "subheading": ParagraphStyle(
            "subheading",
            parent=base["Heading3"],
            fontSize=11,
            textColor=WARM_800,
            spaceBefore=10,
            spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["Normal"],
            fontSize=10,
            textColor=WARM_800,
            leading=14,
            spaceAfter=6,
        ),
        "step": ParagraphStyle(
            "step",
            parent=base["Normal"],
            fontSize=10,
            textColor=WARM_800,
            leading=14,
            leftIndent=20,
            spaceAfter=4,
        ),
        "note": ParagraphStyle(
            "note",
            parent=base["Normal"],
            fontSize=9,
            textColor=WARM_600,
            leading=12,
            spaceAfter=4,
        ),
        "footer": ParagraphStyle(
            "footer",
            parent=base["Normal"],
            fontSize=9,
            textColor=WARM_600,
            alignment=TA_CENTER,
        ),
    }
    return styles


def generate(cafe_name="Your Cafe"):
    """Generate the onboarding PDF and return the temp file path."""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    tmp.close()

    doc = SimpleDocTemplate(
        tmp.name,
        pagesize=letter,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        leftMargin=0.85 * inch,
        rightMargin=0.85 * inch,
    )

    styles = _build_styles()
    story = []

    # ── Header ──────────────────────────────────────────
    story.append(Paragraph("Welcome to PulpIQ", styles["title"]))
    story.append(Paragraph(
        f"Getting started guide for {cafe_name}",
        styles["subtitle"],
    ))
    story.append(HRFlowable(
        width="100%", thickness=1, color=WARM_200,
        spaceAfter=16,
    ))

    # ── Intro ───────────────────────────────────────────
    story.append(Paragraph(
        "To see your first insights, we need a CSV export of your sales data. "
        "This guide shows you exactly how to get it from your POS system. "
        "The whole process takes about 2 minutes.",
        styles["body"],
    ))
    story.append(Spacer(1, 8))

    # ── What we need ────────────────────────────────────
    story.append(Paragraph("What We Need", styles["heading"]))
    story.append(Paragraph(
        "A CSV file with your sales transactions. Most POS exports include "
        "everything we need automatically.",
        styles["body"],
    ))

    col_data = [
        ["Column", "Required?", "Example"],
        ["Date", "Yes", "2025-01-15"],
        ["Time", "Yes", "09:30"],
        ["Item Name", "Yes", "Oat Milk Latte"],
        ["Quantity", "Yes", "1"],
        ["Price / Total", "Yes", "5.25"],
        ["Category", "Optional", "Beverage"],
        ["Payment Method", "Optional", "Credit Card"],
    ]
    col_table = Table(col_data, colWidths=[1.8 * inch, 1.2 * inch, 2.5 * inch])
    col_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), WARM_200),
        ("TEXTCOLOR", (0, 0), (-1, 0), WARM_800),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("GRID", (0, 0), (-1, -1), 0.5, WARM_200),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [HexColor("#ffffff"), HexColor("#faf7f5")]),
    ]))
    story.append(col_table)
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "Column names don't have to match exactly — we auto-detect 40+ variations "
        "(e.g., \"Sale Date\", \"Transaction Date\", \"Order Date\" all work for Date).",
        styles["note"],
    ))

    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "<b>How much data:</b> 90 days is ideal. 30 days is good. "
        "7 days minimum (estimates will be rougher).",
        styles["body"],
    ))

    # ── Square ──────────────────────────────────────────
    story.append(Paragraph("Exporting from Square", styles["heading"]))
    steps = [
        "Log in to your <b>Square Dashboard</b> (squareup.com/dashboard)",
        "Go to <b>Reports</b> in the left sidebar",
        "Click <b>Sales</b> (or \"Sales Summary\")",
        "Set the date range to <b>the last 90 days</b>",
        "Click the <b>Export</b> button (top right) and choose <b>\"Item Detail\"</b>",
        "Choose <b>CSV</b> format and download",
    ]
    for i, step in enumerate(steps, 1):
        story.append(Paragraph(f"<b>{i}.</b> {step}", styles["step"]))
    story.append(Paragraph(
        "Important: Choose \"Item Detail\", not \"Summary\". "
        "Summary groups items together and loses the transaction-level detail we need.",
        styles["note"],
    ))

    # ── Toast ───────────────────────────────────────────
    story.append(Paragraph("Exporting from Toast", styles["heading"]))
    steps = [
        "Log in to <b>Toast Web</b> (pos.toasttab.com)",
        "Go to <b>Reports</b> > <b>Sales Summary</b>",
        "Set the date range to <b>the last 90 days</b>",
        "Click <b>Export</b> and choose <b>\"Transaction Detail\"</b> format",
        "Download as <b>CSV</b>",
    ]
    for i, step in enumerate(steps, 1):
        story.append(Paragraph(f"<b>{i}.</b> {step}", styles["step"]))
    story.append(Paragraph(
        "If you don't see \"Transaction Detail\", try Reports > Payments > Export. "
        "Any export that shows individual items sold with dates and prices works.",
        styles["note"],
    ))

    # ── Clover ──────────────────────────────────────────
    story.append(Paragraph("Exporting from Clover", styles["heading"]))
    steps = [
        "Log in to your <b>Clover Web Dashboard</b>",
        "Go to <b>Reporting</b> > <b>Transactions</b>",
        "Set the date range to <b>the last 90 days</b>",
        "Click <b>Export</b> (top right)",
        "Download the <b>CSV</b> file",
    ]
    for i, step in enumerate(steps, 1):
        story.append(Paragraph(f"<b>{i}.</b> {step}", styles["step"]))

    # ── Other POS ───────────────────────────────────────
    story.append(Paragraph("Other POS Systems", styles["heading"]))
    story.append(Paragraph(
        "If you use a different POS (Lightspeed, Shopify, Revel, etc.), look for a "
        "\"Sales Report\" or \"Transaction Report\" export option. As long as the CSV "
        "has date, time, item name, quantity, and price columns, it'll work.",
        styles["body"],
    ))

    # ── What's next ─────────────────────────────────────
    story.append(Spacer(1, 12))
    story.append(HRFlowable(
        width="100%", thickness=1, color=WARM_200,
        spaceAfter=12,
    ))
    story.append(Paragraph("What Happens Next", styles["heading"]))
    story.append(Paragraph(
        "<b>1.</b> Click the sign-in link in this email to log in<br/>"
        "<b>2.</b> Click \"Upload Data\" and drag in your CSV file<br/>"
        "<b>3.</b> See your instant report — revenue insights, waste analysis, and savings estimate<br/>"
        "<b>4.</b> Come back next week with a new export to track your progress",
        styles["body"],
    ))

    # ── Footer ──────────────────────────────────────────
    story.append(Spacer(1, 20))
    story.append(HRFlowable(
        width="100%", thickness=0.5, color=WARM_200,
        spaceAfter=8,
    ))
    story.append(Paragraph(
        "Questions? Reply to this email or reach us at hello@pulpiq.io",
        styles["footer"],
    ))
    story.append(Paragraph(
        "PulpIQ — Stop Guessing. Start Saving. | pulpiq.io",
        styles["footer"],
    ))

    doc.build(story)
    return tmp.name
