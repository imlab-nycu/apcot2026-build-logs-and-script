from __future__ import annotations

import csv
import json
import subprocess
from collections import OrderedDict
from pathlib import Path

from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import registerFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "derived" / "APCOT2026_public_v10_proceedings_manifest_authors_clean.csv"
OUTPUT_PDF = ROOT / "derived" / "APCOT2026_public_v10_toc_pages.pdf"
BUILD_LOG = ROOT / "derived" / "APCOT2026_public_v10_toc_build_log.json"


def find_font(name: str) -> Path:
    result = subprocess.check_output(["fc-match", "-f", "%{file}\n", name], text=True).strip()
    if not result:
        raise RuntimeError(f"Unable to resolve font: {name}")
    return Path(result)


def roman_numeral(value: int) -> str:
    numerals = [
        (1000, "M"),
        (900, "CM"),
        (500, "D"),
        (400, "CD"),
        (100, "C"),
        (90, "XC"),
        (50, "L"),
        (40, "XL"),
        (10, "X"),
        (9, "IX"),
        (5, "V"),
        (4, "IV"),
        (1, "I"),
    ]
    result = []
    remaining = value
    for arabic, roman in numerals:
        while remaining >= arabic:
            result.append(roman)
            remaining -= arabic
    return "".join(result)


def wrap(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def load_records() -> list[dict[str, str]]:
    with MANIFEST.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def build_story(records: list[dict[str, str]], body_font: str, body_bold: str):
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "Title",
        parent=styles["Title"],
        fontName=body_bold,
        fontSize=11.8,
        leading=13.2,
        alignment=TA_LEFT,
        spaceAfter=1,
        spaceBefore=0,
    )
    heading_style = ParagraphStyle(
        "Heading",
        parent=styles["Heading2"],
        fontName=body_bold,
        fontSize=8.0,
        leading=9.2,
        spaceBefore=1,
        spaceAfter=2,
    )
    entry_line_style = ParagraphStyle(
        "EntryLine",
        parent=styles["BodyText"],
        fontName=body_bold,
        fontSize=6.8,
        leading=7.5,
        leftIndent=0,
        firstLineIndent=0,
        spaceBefore=0,
        spaceAfter=0,
    )
    entry_title_style = ParagraphStyle(
        "EntryTitle",
        parent=styles["BodyText"],
        fontName=body_font,
        fontSize=7.0,
        leading=7.8,
        leftIndent=3,
        firstLineIndent=0,
        spaceBefore=0,
        spaceAfter=0,
    )
    entry_authors_style = ParagraphStyle(
        "EntryAuthors",
        parent=styles["BodyText"],
        fontName=body_font,
        fontSize=6.5,
        leading=7.1,
        textColor="#111111",
        leftIndent=6,
        firstLineIndent=0,
        spaceBefore=0,
        spaceAfter=0,
    )

    story = [Paragraph("Table of Contents", title_style), Spacer(1, 0.15 * mm)]
    grouped: OrderedDict[tuple[str, str], list[dict[str, str]]] = OrderedDict()
    for row in records:
        key = (row["day"], row["session_label"])
        grouped.setdefault(key, []).append(row)

    for index, ((day, session_label), items) in enumerate(grouped.items()):
        story.append(Paragraph(f"{wrap(day)} / {wrap(session_label)}", heading_style))
        for item in items:
            page_text = item["start_page"] if item["start_page"] == item["end_page"] else f"{item['start_page']}-{item['end_page']}"
            leader = "." * 130
            story.append(Paragraph(f"ID {wrap(item['id'])} {leader}<br/>{wrap(page_text)}", entry_line_style))
            story.append(Paragraph(wrap(item["title"]), entry_title_style))
            story.append(Paragraph(wrap(item["authors"]), entry_authors_style))
        if index < len(grouped) - 1:
            story.append(Spacer(1, 0.1 * mm))

    return story


def build_pdf() -> dict[str, str | int]:
    records = load_records()
    regular_font = find_font("Noto Sans")
    bold_font = find_font("Noto Sans Bold")
    registerFont(TTFont("APCOTNotoSans", str(regular_font)))
    registerFont(TTFont("APCOTNotoSans-Bold", str(bold_font)))

    doc = SimpleDocTemplate(
        str(OUTPUT_PDF),
        pagesize=A4,
        leftMargin=10 * mm,
        rightMargin=10 * mm,
        topMargin=10 * mm,
        bottomMargin=9 * mm,
    )

    story = build_story(records, "APCOTNotoSans", "APCOTNotoSans-Bold")

    def on_page(canvas, _doc):
        page_number = canvas.getPageNumber()
        canvas.setFont("APCOTNotoSans", 8.6)
        canvas.drawCentredString(A4[0] / 2, 9 * mm, roman_numeral(page_number))

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)

    return {
        "manifest_csv": str(MANIFEST.relative_to(ROOT)),
        "output_pdf": str(OUTPUT_PDF.relative_to(ROOT)),
        "record_count": len(records),
    }


def main() -> None:
    summary = build_pdf()
    BUILD_LOG.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()