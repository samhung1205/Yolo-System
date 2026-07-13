"""Render deterministic detection Markdown as a polished PDF."""
from __future__ import annotations

from functools import lru_cache
from html import escape
from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    LongTable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    TableStyle,
)

_FONT_CANDIDATES = (
    Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
    Path("/System/Library/Fonts/STHeiti Light.ttc"),
)


@lru_cache(maxsize=1)
def _report_font_name() -> str:
    for path in _FONT_CANDIDATES:
        if not path.is_file() or path.stat().st_size < 1024:
            continue
        try:
            pdfmetrics.registerFont(TTFont("YoloReportUnicode", str(path)))
            return "YoloReportUnicode"
        except Exception:
            continue
    return "Helvetica"


def _styles() -> dict[str, ParagraphStyle]:
    font = _report_font_name()
    sample = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "ReportTitle",
            parent=sample["Title"],
            fontName=font,
            fontSize=20,
            leading=24,
            textColor=colors.HexColor("#17324D"),
            alignment=TA_CENTER,
            spaceAfter=5 * mm,
        ),
        "heading": ParagraphStyle(
            "ReportHeading",
            parent=sample["Heading2"],
            fontName=font,
            fontSize=12,
            leading=15,
            textColor=colors.HexColor("#0C6DFD"),
            spaceBefore=2.5 * mm,
            spaceAfter=1 * mm,
        ),
        "body": ParagraphStyle(
            "ReportBody",
            parent=sample["BodyText"],
            fontName=font,
            fontSize=8.4,
            leading=11.2,
            textColor=colors.HexColor("#243B53"),
            spaceAfter=0.7 * mm,
        ),
        "bullet": ParagraphStyle(
            "ReportBullet",
            parent=sample["BodyText"],
            fontName=font,
            fontSize=8.4,
            leading=11.2,
            leftIndent=5 * mm,
            firstLineIndent=-3 * mm,
            textColor=colors.HexColor("#243B53"),
            spaceAfter=0.5 * mm,
        ),
        "table": ParagraphStyle(
            "ReportTable",
            parent=sample["BodyText"],
            fontName=font,
            fontSize=6.8,
            leading=8.5,
            textColor=colors.HexColor("#243B53"),
        ),
    }


def _table_from_lines(lines: list[str], styles: dict[str, ParagraphStyle]):
    rows: list[list[Paragraph]] = []
    for line in lines:
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells and all(set(cell) <= {"-", ":"} for cell in cells):
            continue
        rows.append([Paragraph(escape(cell), styles["table"]) for cell in cells])
    if not rows:
        return None

    available_width = A4[0] - 36 * mm
    if len(rows[0]) == 4:
        widths = [12 * mm, 35 * mm, 27 * mm, available_width - 74 * mm]
    else:
        widths = [available_width / len(rows[0])] * len(rows[0])
    table = LongTable(rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAF2FD")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#17324D")),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#C9D6E2")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
                    colors.white,
                    colors.HexColor("#F8FAFC"),
                ]),
            ]
        )
    )
    return table


def _story_from_markdown(markdown: str):
    styles = _styles()
    story = []
    lines = markdown.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        if not line:
            story.append(Spacer(1, 0.6 * mm))
        elif line.startswith("# "):
            story.append(Paragraph(escape(line[2:].strip()), styles["title"]))
        elif line.startswith("## "):
            story.append(Paragraph(escape(line[3:].strip()), styles["heading"]))
        elif line == "---":
            story.append(
                HRFlowable(
                    width="100%",
                    thickness=0.6,
                    color=colors.HexColor("#C9D6E2"),
                    spaceBefore=3 * mm,
                    spaceAfter=3 * mm,
                )
            )
        elif line.startswith("|"):
            table_lines = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                table_lines.append(lines[index].strip())
                index += 1
            index -= 1
            table = _table_from_lines(table_lines, styles)
            if table is not None:
                story.append(table)
        elif line.startswith("- "):
            story.append(
                Paragraph(f"• {escape(line[2:].strip())}", styles["bullet"])
            )
        else:
            story.append(
                Paragraph(escape(line.strip("_")), styles["body"])
            )
        index += 1
    return story


def render_markdown_pdf(markdown: str, *, detection_id: int) -> bytes:
    """Return a PDF byte string for deterministic report Markdown."""
    if not markdown.strip():
        raise ValueError("Report Markdown must not be empty.")

    buffer = BytesIO()
    font = _report_font_name()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=12 * mm,
        bottomMargin=16 * mm,
        title=f"YOLO Detection Report {detection_id}",
        author="YOLO Detection and Intelligent Analysis Platform",
    )

    def draw_page(canvas, doc) -> None:
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#D9E2EC"))
        canvas.setLineWidth(0.5)
        canvas.line(18 * mm, 14 * mm, A4[0] - 18 * mm, 14 * mm)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#627D98"))
        canvas.drawString(
            18 * mm,
            9 * mm,
            "YOLO Detection and Intelligent Analysis Platform",
        )
        canvas.drawRightString(
            A4[0] - 18 * mm,
            9 * mm,
            f"Detection {detection_id}  |  Page {doc.page}",
        )
        canvas.restoreState()

    document.build(
        _story_from_markdown(markdown),
        onFirstPage=draw_page,
        onLaterPages=draw_page,
    )
    return buffer.getvalue()
