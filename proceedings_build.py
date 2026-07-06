from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import subprocess
import unicodedata
from collections import OrderedDict
from io import BytesIO
from dataclasses import dataclass
from typing import Any, Callable
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import registerFont
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def parse_version_tag(value: str) -> tuple[int, str]:
    match = re.fullmatch(r"v(\d+)([a-z]?)", value)
    if not match:
        return (-1, value)
    return (int(match.group(1)), match.group(2))


def detect_latest_html_index(root: Path) -> Path:
    candidates = sorted(
        root.glob("apcot2026_abstract_index_v*.html"),
        key=lambda path: parse_version_tag(path.stem.rsplit("_", 1)[-1]),
    )
    if not candidates:
        raise RuntimeError("Unable to locate any apcot2026_abstract_index_v*.html file")
    return candidates[-1]


ROOT = Path(__file__).resolve().parent
DERIVED = ROOT / "derived"
PROJECT = "APCOT2026"
PUBLIC_LABEL = "public"
VERSION = "v14"
PREVIOUS_VERSION = "v13"


def public_release_name(version: str, suffix: str) -> str:
    return f"{PROJECT}_{PUBLIC_LABEL}_{version}_{suffix}"


def proceedings_pdf_name(version: str, suffix: str = "") -> str:
    base_name = f"{PROJECT}_Abstract_Proceedings_{PUBLIC_LABEL}_{version}"
    return f"{base_name}_{suffix}" if suffix else base_name


HTML_INDEX = detect_latest_html_index(ROOT)
SOURCE_MANIFEST = DERIVED / f"{public_release_name(PREVIOUS_VERSION, 'proceedings_manifest_authors_clean')}.csv"
MANIFEST_CSV = DERIVED / f"{public_release_name(VERSION, 'proceedings_manifest_authors_clean')}.csv"
REORDER_LOG = DERIVED / f"{public_release_name(VERSION, 'reorder_log')}.json"
TOC_PDF = DERIVED / f"{public_release_name(VERSION, 'toc_pages')}.pdf"
TOC_BUILD_LOG = DERIVED / f"{public_release_name(VERSION, 'toc_build_log')}.json"
TOC_FRONT_MATTER = DERIVED / f"{public_release_name(VERSION, 'front_matter')}.pdf"
TOC_FRONT_MATTER_LOG = DERIVED / f"{public_release_name(VERSION, 'front_matter_build_log')}.json"
FRONT_MATTER_SOURCE = DERIVED / f"{public_release_name(PREVIOUS_VERSION, 'front_matter')}.pdf"
FINAL_PDF = DERIVED / f"{proceedings_pdf_name(VERSION)}.pdf"
FINAL_BUILD_LOG = DERIVED / f"{public_release_name(VERSION, 'build_log')}.json"
NUMBERED_PDF = DERIVED / f"{proceedings_pdf_name(VERSION, 'numbered')}.pdf"
NUMBERED_BUILD_LOG = DERIVED / f"{public_release_name(VERSION, 'numbered_build_log')}.json"
COMPRESSED_PDF = DERIVED / f"{proceedings_pdf_name(VERSION, 'numbered_compressed')}.pdf"
COMPRESSED_BUILD_LOG = DERIVED / f"{public_release_name(VERSION, 'numbered_compressed_build_log')}.json"

MANIFEST_FIELDS = [
    "id",
    "code",
    "day",
    "session_label",
    "session_time",
    "time",
    "room",
    "title",
    "authors",
    "affiliations",
    "source_pdf",
    "source_pages",
    "start_page",
    "end_page",
]

SUBSCRIPT_MARKUP = {
    "₀": "<sub>0</sub>",
    "₁": "<sub>1</sub>",
    "₂": "<sub>2</sub>",
    "₃": "<sub>3</sub>",
    "₄": "<sub>4</sub>",
    "₅": "<sub>5</sub>",
    "₆": "<sub>6</sub>",
    "₇": "<sub>7</sub>",
    "₈": "<sub>8</sub>",
    "₉": "<sub>9</sub>",
    "ₓ": "<sub>x</sub>",
}


@dataclass(frozen=True)
class PipelineStage:
    name: str
    description: str
    output: Path
    inputs: Callable[[], list[Path]]
    action: Callable[[bool], dict[str, Any]]


def build_manifest_stage(force: bool = False) -> dict[str, str | int | list[str]]:
    if force or needs_rebuild(MANIFEST_CSV, stage_inputs_for_manifest()):
        return build_manifest_from_html()
    return read_json(REORDER_LOG)


def build_toc_stage(force: bool = False) -> dict[str, str | int]:
    if force or needs_rebuild(TOC_PDF, stage_inputs_for_toc()):
        return build_toc_pdf(MANIFEST_CSV)
    return read_json(TOC_BUILD_LOG)


def build_front_matter_stage(force: bool = False) -> dict[str, str | int]:
    if force or needs_rebuild(TOC_FRONT_MATTER, stage_inputs_for_front_matter()):
        return build_front_matter_pdf()
    return read_json(TOC_FRONT_MATTER_LOG)


def build_final_stage(force: bool = False) -> dict[str, str | int | list[str]]:
    if force or needs_rebuild(FINAL_PDF, stage_inputs_for_final()):
        return build_final_proceedings_pdf()
    return read_json(FINAL_BUILD_LOG)


def build_numbered_stage(force: bool = False) -> dict[str, str | int]:
    if force or needs_rebuild(NUMBERED_PDF, stage_inputs_for_numbered()):
        return build_numbered_proceedings_pdf()
    return read_json(NUMBERED_BUILD_LOG)


def build_compressed_stage(force: bool = False) -> dict[str, str | float | int]:
    if force or needs_rebuild(COMPRESSED_PDF, stage_inputs_for_compression()):
        return build_compressed_pdf()
    return read_json(COMPRESSED_BUILD_LOG)


def get_stage(name: str) -> PipelineStage:
    for stage in PIPELINE_STAGES:
        if stage.name == name:
            return stage
    raise KeyError(name)


def stage_log_path(stage_name: str) -> Path:
    return {
        "manifest": REORDER_LOG,
        "toc": TOC_BUILD_LOG,
        "front-matter": TOC_FRONT_MATTER_LOG,
        "final": FINAL_BUILD_LOG,
        "numbered": NUMBERED_BUILD_LOG,
        "compressed": COMPRESSED_BUILD_LOG,
    }[stage_name]


def run_stage(stage_name: str, force: bool = False) -> dict[str, Any]:
    stage = get_stage(stage_name)
    if force or needs_rebuild(stage.output, stage.inputs()):
        return stage.action(True)
    return read_json(stage_log_path(stage_name))


def run_pipeline(stage_names: list[str] | None = None, force: bool = False) -> list[tuple[str, dict[str, Any]]]:
    selected = PIPELINE_STAGES if stage_names is None else [get_stage(name) for name in stage_names]
    results: list[tuple[str, dict[str, Any]]] = []
    for stage in selected:
        results.append((stage.name, run_stage(stage.name, force=force)))
    return results


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict) -> None:
    ensure_parent(path)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def sha256sum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def file_mtime(path: Path) -> int:
    return path.stat().st_mtime_ns


def needs_rebuild(output: Path, inputs: list[Path], extra_inputs: list[Path] | None = None) -> bool:
    all_inputs = list(inputs)
    if extra_inputs:
        all_inputs.extend(extra_inputs)
    if not output.exists():
        return True
    output_mtime = file_mtime(output)
    for item in all_inputs:
        if not item.exists():
            return True
        if file_mtime(item) > output_mtime:
            return True
    return False


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


def normalize_toc_text(text: str) -> str:
    normalized = unicodedata.normalize("NFC", text)
    normalized = normalized.replace("、", ", ")
    normalized = wrap(normalized)
    for source, target in SUBSCRIPT_MARKUP.items():
        normalized = normalized.replace(source, target)
    return normalized


def load_html_records(path: Path = HTML_INDEX) -> list[dict[str, str]]:
    html = path.read_text(encoding="utf-8")
    match = re.search(r"const records = (\[.*?\]);\s*const stats =", html, re.S)
    if not match:
        raise RuntimeError(f"Unable to locate embedded records array in {path}")
    records = json.loads(match.group(1))
    return [dict(record) for record in records]


def choose_manifest_records(records: list[dict[str, str]]) -> list[dict[str, str]]:
    chosen: dict[str, tuple[int, dict[str, str]]]
    chosen = {}
    for index, record in enumerate(records):
        record_id = record["id"]
        current = chosen.get(record_id)
        if current is None:
            chosen[record_id] = (index, record)
            continue
        current_index, current_record = current
        current_is_poster = current_record["session_label"].startswith("Poster Session")
        next_is_poster = record["session_label"].startswith("Poster Session")
        if current_is_poster and not next_is_poster:
            chosen[record_id] = (index, record)
    ordered = sorted(chosen.values(), key=lambda item: item[0])
    return [record for _, record in ordered]


def infer_source_root(default: Path | None = None) -> Path:
    if value := os.environ.get("APCOT_SOURCE_ROOT"):
        return Path(value).expanduser().resolve()
    if MANIFEST_CSV.exists():
        with MANIFEST_CSV.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            first = next(reader, None)
        if first and first.get("source_pdf"):
            source_pdf = Path(first["source_pdf"])
            return source_pdf.parent.parent.resolve()
    return (default or ROOT).resolve()


def write_manifest_csv(rows: list[dict[str, str]], output_path: Path) -> None:
    ensure_parent(output_path)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def build_manifest_from_html(
    html_path: Path = HTML_INDEX,
    output_manifest: Path = MANIFEST_CSV,
    reorder_log: Path = REORDER_LOG,
    source_root: Path | None = None,
) -> dict[str, str | int | list[str]]:
    raw_records = load_html_records(html_path)
    manifest_records = choose_manifest_records(raw_records)
    grouped_records: OrderedDict[tuple[str, str], list[dict[str, str]]] = OrderedDict()
    for record in manifest_records:
        key = (record["day"], record["session_label"])
        grouped_records.setdefault(key, []).append(record)
    ordered_records = [record for items in grouped_records.values() for record in items]
    source_root = infer_source_root(source_root)
    cleanup_manifest = MANIFEST_CSV if MANIFEST_CSV.exists() else SOURCE_MANIFEST
    author_cleanup: dict[str, str] = {}
    if cleanup_manifest.exists():
        for row in load_manifest_rows(cleanup_manifest):
            author_cleanup[row["id"]] = row.get("authors", "")

    resolved_rows: list[dict[str, str]] = []
    cursor = 1
    session_groups: OrderedDict[tuple[str, str], list[str]] = OrderedDict()
    missing_pdfs: list[str] = []

    for record in ordered_records:
        source_pdf = (source_root / "APCOT_Abstract" / f"{record['id']}.pdf").resolve()
        if not source_pdf.exists():
            missing_pdfs.append(str(source_pdf))
            source_pages = 0
        else:
            source_pages = len(PdfReader(str(source_pdf)).pages)
        start_page = cursor
        end_page = cursor + source_pages - 1
        cursor = end_page + 1
        session_groups.setdefault((record["day"], record["session_label"]), []).append(record["id"])
        
        row_title = record.get("title", "")
        row_authors = author_cleanup.get(record["id"], record.get("authors", ""))
        
        # --- APPLIED FIXES (v14) ---
        r_id = record["id"]
        if r_id == '0236':
            row_title = "Control of Strain Response in Modal-Interference-Based Plastic Optical Fiber Sensors via Double-Side Reactive Ion Etching"
            row_authors = "Motoki Kochi, Koyo Shibuta, Keito Ishida, Yuri Wada, Taiki Kumagai, Keita S. Shirai, C.-Y. Lo, H. Lee, Y. Mizuno, D. Yamane"
        elif r_id == '0201':
            row_title = "Enhanced Suppression of Non-Specific Adsorption of Graphene Oxide-Based Resonant Sensor for Label-Free Virus Sensing"
            row_authors = "Viet Khoa Pham, Laoyang Yiayee, Homare Yoshida, Sachiko Sakai, Ippei Akita, Yasuyuki Imaizumi, Tatsuro Goda, I.-H. Kwon, Y.-J. Choi, T. Noda, K. Sawada, K. Takahashi"
        elif r_id == '0235':
            row_title = "Tri-Layer Soft-Rigid Stretchable Substrates for Direct Fabrication Stretchable Electronics Device"
            row_authors = "Shusuke Yamakoshi, Fumika Nakamura, Sho Sato, Yuji Isano, Yutaka Isoda, Ryosuke Matsuda, Naoko Namba, Tsuyoshi Sekitani, Takafumi Uemura, Hiroki Ota"
        elif r_id == '0426':
            row_title = "Multifunctional Nanostructured Biosensor Platform Integrating Electrical, Optical Transduction Mechanisms"
            row_authors = "Hung-Hsiang Wang, Yu-Quan Chen, Chih-Ting Lin"
            
        subs = {
            '0218': [('Ti3C2Tx', 'Ti₃C₂Tₓ')],
            '0188': [('BaTiO3', 'BaTiO₃')],
            '0278': [('MoS2', 'MoS₂')],
            '0192': [('0.4Pb(Mg1/3Nb2/3)O3–0.22PbZrO3-0.38PbTiO3', '0.4Pb(Mg₁/₃Nb₂/₃)O₃–0.22PbZrO₃-0.38PbTiO₃')],
            '0320': [('WS2/Ga2O3', 'WS₂/Ga₂O₃')],
            '0341': [('Al2O3', 'Al₂O₃'), ('SnO2', 'SnO₂')],
            '0303': [('TiO2', 'TiO₂')],
            '0346': [('Al2O3', 'Al₂O₃')],
            '0354': [('Ta2O5', 'Ta₂O₅')],
            '0328': [('Fe3O4', 'Fe₃O₄')],
            '0358': [('SiO2', 'SiO₂')],
        }
        if r_id in subs:
            for old, new in subs[r_id]:
                row_title = row_title.replace(old, new)
                
        if r_id == '0447': row_authors = "Fuyang Qu, Luoquan Li, Juan Li, Guangyao Cheng, Yi-Ping Ho"
        elif r_id == '0430': row_authors = "Guangyao Cheng, Luoquan Li, Weilun Liu, Silin Zhong, Yi-Ping Ho"
        elif r_id == '0454': row_authors = "Yi-Hsien Wu, Ching-Kai Lin, Chen-Wei Chang, Chin-Chung Chen, Shu-Chung Lee, Yun-Chien Cheng, Tien-Kan Chung"
        elif r_id == '0253': row_authors = "Qinru Xiao, Guangyao Cheng, Kuan Wen Lou, Yi-Ping Ho"
        elif r_id == '0416': row_authors = "Yi-Jing Liao, Shu-Ping Lin"
        # ---------------------------

        resolved_rows.append(
            {
                "id": record["id"],
                "code": record.get("code", record["id"]),
                "day": record["day"],
                "session_label": record["session_label"],
                "session_time": record.get("session_time", ""),
                "time": record.get("time", ""),
                "room": record.get("room", ""),
                "title": row_title,
                "authors": row_authors,
                "affiliations": record.get("affiliations", ""),
                "source_pdf": str(source_pdf),
                "source_pages": str(source_pages),
                "start_page": str(start_page),
                "end_page": str(end_page),
            }
        )

    # Reorder rows to fix A/B/C/D/E sequence issues
    def day_to_int(d_str):
        if "Monday" in d_str: return 1
        if "Tuesday" in d_str: return 2
        if "Wednesday" in d_str: return 3
        return 4
    resolved_rows.sort(key=lambda r: (day_to_int(r["day"]), r["session_time"], r["session_label"], r["time"]))
    
    # Recalculate pages since reordering changes the page numbers
    cursor = 1
    for r in resolved_rows:
        p_count = int(r["source_pages"])
        r["start_page"] = str(cursor)
        r["end_page"] = str(cursor + p_count - 1) if p_count > 0 else str(cursor)
        cursor += p_count

    write_manifest_csv(resolved_rows, output_manifest)

    summary = {
        "source_manifest": str(SOURCE_MANIFEST.relative_to(ROOT)),
        "output_manifest": display_path(output_manifest),
        "rows": len(resolved_rows),
        "session_group_count": len(session_groups),
        "last_abstract_page": cursor - 1,
        "first10_ids": [row["id"] for row in resolved_rows[:10]],
        "last10_ids": [row["id"] for row in resolved_rows[-10:]],
    }
    if missing_pdfs:
        summary["missing_pdfs"] = missing_pdfs
    write_json(reorder_log, summary)
    return summary


def load_manifest_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def build_toc_pdf(
    manifest_csv: Path,
    output_pdf: Path = TOC_PDF,
    build_log: Path = TOC_BUILD_LOG,
) -> dict[str, str | int]:
    records = load_manifest_rows(manifest_csv)
    regular_font = find_font("Noto Sans")
    bold_font = find_font("Noto Sans Bold")
    registerFont(TTFont("APCOTNotoSans", str(regular_font)))
    registerFont(TTFont("APCOTNotoSans-Bold", str(bold_font)))

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "Title",
        parent=styles["Title"],
        fontName="APCOTNotoSans-Bold",
        fontSize=11.8,
        leading=13.2,
        alignment=TA_LEFT,
        spaceAfter=1,
        spaceBefore=0,
    )
    heading_style = ParagraphStyle(
        "Heading",
        parent=styles["Heading2"],
        fontName="APCOTNotoSans-Bold",
        fontSize=8.0,
        leading=9.2,
        spaceBefore=1,
        spaceAfter=2,
    )
    entry_line_style = ParagraphStyle(
        "EntryLine",
        parent=styles["BodyText"],
        fontName="APCOTNotoSans-Bold",
        fontSize=7.6,
        leading=8.3,
        leftIndent=0,
        firstLineIndent=0,
        spaceBefore=0,
        spaceAfter=0,
    )
    entry_title_style = ParagraphStyle(
        "EntryTitle",
        parent=styles["BodyText"],
        fontName="APCOTNotoSans",
        fontSize=7.8,
        leading=8.7,
        leftIndent=4,
        firstLineIndent=0,
        spaceBefore=0,
        spaceAfter=0,
    )
    entry_authors_style = ParagraphStyle(
        "EntryAuthors",
        parent=styles["BodyText"],
        fontName="APCOTNotoSans",
        fontSize=7.2,
        leading=7.9,
        textColor="#111111",
        leftIndent=8,
        firstLineIndent=0,
        spaceBefore=0,
        spaceAfter=0,
    )

    page_width = A4[0]
    usable_width = page_width - (doc_left := 10 * mm) - (doc_right := 10 * mm)

    def build_entry_row(item_id: str, page_text: str) -> Table:
        prefix = f"ID {wrap(item_id)} "
        font_name = entry_line_style.fontName
        font_size = entry_line_style.fontSize
        dots_width = pdfmetrics.stringWidth(".", font_name, font_size)
        prefix_width = pdfmetrics.stringWidth(f"ID {item_id} ", font_name, font_size)
        page_col_width = 16 * mm
        available = max(0.0, usable_width - page_col_width - prefix_width - 2.0)
        dots_count = max(24, int(available / max(dots_width, 0.1)))
        left_text = f"{prefix}{'.' * dots_count}"
        row = Table(
            [[Paragraph(left_text, entry_line_style), Paragraph(wrap(page_text), entry_line_style)]],
            colWidths=[usable_width - page_col_width, page_col_width],
        )
        row.setStyle(
            TableStyle(
                [
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                ]
            )
        )
        return row

    story = [Paragraph("Table of Contents", title_style), Spacer(1, 0.15 * mm)]
    grouped: OrderedDict[tuple[str, str], list[dict[str, str]]] = OrderedDict()
    for row in records:
        key = (row["day"], row["session_label"])
        grouped.setdefault(key, []).append(row)

    for index, ((day, session_label), items) in enumerate(grouped.items()):
        story.append(Paragraph(f"{wrap(day)} / {wrap(session_label)}", heading_style))
        for item in items:
            page_text = item["start_page"] if item["start_page"] == item["end_page"] else f"{item['start_page']}-{item['end_page']}"
            story.append(build_entry_row(item["id"], page_text))
            story.append(Paragraph(normalize_toc_text(item["title"]), entry_title_style))
            story.append(Paragraph(normalize_toc_text(item["authors"]), entry_authors_style))
        if index < len(grouped) - 1:
            story.append(Spacer(1, 0.1 * mm))

    doc = SimpleDocTemplate(
        str(output_pdf),
        pagesize=A4,
        leftMargin=doc_left,
        rightMargin=doc_right,
        topMargin=10 * mm,
        bottomMargin=9 * mm,
    )

    def on_page(canvas, _doc):
        page_number = canvas.getPageNumber()
        canvas.setFont("APCOTNotoSans", 8.6)
        canvas.drawCentredString(A4[0] / 2, 9 * mm, roman_numeral(page_number))

    ensure_parent(output_pdf)
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    summary = {
        "manifest_csv": display_path(manifest_csv),
        "output_pdf": display_path(output_pdf),
        "record_count": len(records),
    }
    write_json(build_log, summary)
    return summary


def merge_pdfs(input_paths: list[Path], output_path: Path) -> None:
    writer = PdfWriter()
    for path in input_paths:
        writer.append(str(path))
    ensure_parent(output_path)
    with output_path.open("wb") as handle:
        writer.write(handle)


def build_front_matter_pdf(
    cover_source: Path = FRONT_MATTER_SOURCE,
    toc_source: Path = TOC_PDF,
    output_pdf: Path = TOC_FRONT_MATTER,
    build_log: Path = TOC_FRONT_MATTER_LOG,
) -> dict[str, str | int]:
    cover_reader = PdfReader(str(cover_source))
    toc_start_index: int | None = None
    for index, page in enumerate(cover_reader.pages):
        text = page.extract_text() or ""
        if "Table of Contents" in text:
            toc_start_index = index
            break

    if toc_start_index is None:
        cover_pages_to_keep = len(cover_reader.pages)
    else:
        cover_pages_to_keep = max(1, toc_start_index)

    toc_reader = PdfReader(str(toc_source))
    writer = PdfWriter()
    for page in cover_reader.pages[:cover_pages_to_keep]:
        writer.add_page(page)
    for page in toc_reader.pages:
        writer.add_page(page)

    ensure_parent(output_pdf)
    with output_pdf.open("wb") as handle:
        writer.write(handle)

    summary = {
        "output_pdf": display_path(output_pdf),
        "pages": len(PdfReader(str(output_pdf)).pages),
        "cover_source": display_path(cover_source),
        "toc_source": display_path(toc_source),
        "cover_pages_total": len(cover_reader.pages),
        "cover_pages_used": cover_pages_to_keep,
        "legacy_toc_stripped": toc_start_index is not None,
    }
    write_json(build_log, summary)
    return summary


def build_final_proceedings_pdf(
    manifest_csv: Path = MANIFEST_CSV,
    front_matter_pdf: Path = TOC_FRONT_MATTER,
    output_pdf: Path = FINAL_PDF,
    build_log: Path = FINAL_BUILD_LOG,
) -> dict[str, str | int | list[str]]:
    rows = load_manifest_rows(manifest_csv)
    source_paths: list[Path] = [front_matter_pdf]
    missing_pdfs: list[str] = []
    page_mismatch_samples: list[dict[str, int | str]] = []
    included_pages = 0

    for row in rows:
        source_pdf = Path(row["source_pdf"])
        if not source_pdf.exists():
            source_pdf = (ROOT / row["source_pdf"]).resolve()
        if not source_pdf.exists():
            missing_pdfs.append(row["source_pdf"])
            continue
        actual_pages = len(PdfReader(str(source_pdf)).pages)
        expected_pages = int(row["source_pages"])
        if actual_pages != expected_pages:
            page_mismatch_samples.append({"id": row["id"], "expected": expected_pages, "actual": actual_pages})
        included_pages += actual_pages
        source_paths.append(source_pdf)

    merge_pdfs(source_paths, output_pdf)
    summary = {
        "front_matter_pdf": display_path(front_matter_pdf),
        "manifest_csv": display_path(manifest_csv),
        "final_pdf": display_path(output_pdf),
        "indexed_records": len(rows),
        "front_matter_pages": len(PdfReader(str(front_matter_pdf)).pages),
        "included_abstract_pages": included_pages,
        "final_pdf_pages": len(PdfReader(str(output_pdf)).pages),
        "missing_pdf_count": len(missing_pdfs),
        "page_mismatch_count": len(page_mismatch_samples),
        "final_pdf_sha256": sha256sum(output_pdf),
        "final_pdf_bytes": output_pdf.stat().st_size,
        "missing_pdfs": missing_pdfs,
        "page_mismatch_samples": page_mismatch_samples,
    }
    write_json(build_log, summary)
    return summary


def _render_footer_overlay(width: float, height: float, text: str) -> PdfReader:
    buffer = BytesIO()
    canvas = Canvas(buffer, pagesize=(width, height))
    canvas.setFont("APCOTNotoSans", 8.6)
    canvas.drawCentredString(width / 2, 9 * mm, text)
    canvas.save()
    buffer.seek(0)
    return PdfReader(buffer)


def _render_page_overlay(width: float, height: float, footer_text: str, abstract_id: str | None = None) -> PdfReader:
    buffer = BytesIO()
    canvas = Canvas(buffer, pagesize=(width, height))
    canvas.setFont("APCOTNotoSans", 8.6)
    if abstract_id:
        canvas.drawString(18 * mm, height - 12 * mm, abstract_id)
    canvas.drawCentredString(width / 2, 9 * mm, footer_text)
    canvas.save()
    buffer.seek(0)
    return PdfReader(buffer)


def build_numbered_proceedings_pdf(
    source_pdf: Path = FINAL_PDF,
    output_pdf: Path = NUMBERED_PDF,
    build_log: Path = NUMBERED_BUILD_LOG,
    front_matter_pdf: Path = TOC_FRONT_MATTER,
    front_matter_pages: int | None = None,
    footer_text_format: str = "APCOT 2026 Proceedings   [page]",
) -> dict[str, str | int]:
    reader = PdfReader(str(source_pdf))
    writer = PdfWriter()
    regular_font = find_font("Noto Sans")
    registerFont(TTFont("APCOTNotoSans", str(regular_font)))
    if front_matter_pages is None:
        front_matter_pages = len(PdfReader(str(front_matter_pdf)).pages)

    rows = load_manifest_rows(MANIFEST_CSV)
    abstract_ids_by_page: dict[int, str] = {}
    for row in rows:
        abstract_id = row["code"] or row["id"]
        start_page = int(row["start_page"])
        end_page = int(row["end_page"])
        for page_number in range(start_page, end_page + 1):
            abstract_ids_by_page[page_number] = abstract_id

    for index, page in enumerate(reader.pages):
        if index >= front_matter_pages:
            logical_page = index - front_matter_pages + 1
            footer_text = footer_text_format.replace("[page]", str(logical_page))
            abstract_id = abstract_ids_by_page.get(logical_page)
            overlay_reader = _render_page_overlay(float(page.mediabox.width), float(page.mediabox.height), footer_text, abstract_id)
            page.merge_page(overlay_reader.pages[0])
        writer.add_page(page)

    ensure_parent(output_pdf)
    with output_pdf.open("wb") as handle:
        writer.write(handle)

    summary = {
        "source_pdf": display_path(source_pdf),
        "output_pdf": display_path(output_pdf),
        "front_matter_pdf": display_path(front_matter_pdf),
        "front_matter_pages": front_matter_pages,
        "numbered_abstract_pages": len(reader.pages) - front_matter_pages,
        "first_numbered_pdf_page": front_matter_pages + 1,
        "first_logical_page_number": 1,
        "last_logical_page_number": len(reader.pages) - front_matter_pages,
        "footer_text_format": footer_text_format,
        "output_pdf_pages": len(PdfReader(str(output_pdf)).pages),
        "output_pdf_bytes": output_pdf.stat().st_size,
        "output_pdf_sha256": sha256sum(output_pdf),
    }
    write_json(build_log, summary)
    return summary


def build_compressed_pdf(
    source_pdf: Path = NUMBERED_PDF,
    compressed_pdf: Path = COMPRESSED_PDF,
    build_log: Path = COMPRESSED_BUILD_LOG,
) -> dict[str, str | float | int]:
    ensure_parent(compressed_pdf)
    command = [
        "gs",
        "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.7",
        "-dNOPAUSE",
        "-dBATCH",
        "-dQUIET",
        "-dDetectDuplicateImages=true",
        "-dCompressFonts=true",
        "-dSubsetFonts=true",
        "-dPDFSETTINGS=/ebook",
        f"-sOutputFile={compressed_pdf}",
        str(source_pdf),
    ]
    subprocess.run(command, check=True)
    summary = {
        "source_pdf": display_path(source_pdf),
        "compressed_pdf": display_path(compressed_pdf),
        "source_bytes": source_pdf.stat().st_size,
        "compressed_bytes": compressed_pdf.stat().st_size,
        "source_sha256": sha256sum(source_pdf),
        "compressed_sha256": sha256sum(compressed_pdf),
        "compression_ratio": round(compressed_pdf.stat().st_size / source_pdf.stat().st_size, 4),
        "bytes_saved": source_pdf.stat().st_size - compressed_pdf.stat().st_size,
    }
    write_json(build_log, summary)
    return summary


def stage_inputs_for_manifest() -> list[Path]:
    inputs = [HTML_INDEX]
    return inputs


def stage_inputs_for_toc() -> list[Path]:
    return [MANIFEST_CSV, Path(__file__)]


def stage_inputs_for_front_matter() -> list[Path]:
    return [FRONT_MATTER_SOURCE, TOC_PDF, Path(__file__)]


def stage_inputs_for_final() -> list[Path]:
    inputs = [TOC_FRONT_MATTER, MANIFEST_CSV, Path(__file__)]
    if MANIFEST_CSV.exists():
        with MANIFEST_CSV.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                source_pdf = Path(row["source_pdf"])
                if source_pdf.exists():
                    inputs.append(source_pdf)
                else:
                    inputs.append((ROOT / row["source_pdf"]).resolve())
    return inputs


def stage_inputs_for_numbered() -> list[Path]:
    return [FINAL_PDF, Path(__file__)]


def stage_inputs_for_compression() -> list[Path]:
    return [NUMBERED_PDF]


PIPELINE_STAGES: list[PipelineStage] = [
    PipelineStage("manifest", "Build the cleaned proceedings manifest from the HTML index.", MANIFEST_CSV, stage_inputs_for_manifest, build_manifest_stage),
    PipelineStage("toc", "Build the table-of-contents PDF from the cleaned manifest.", TOC_PDF, stage_inputs_for_toc, build_toc_stage),
    PipelineStage("front-matter", "Merge the front matter cover and TOC pages.", TOC_FRONT_MATTER, stage_inputs_for_front_matter, build_front_matter_stage),
    PipelineStage("final", "Assemble the full proceedings PDF.", FINAL_PDF, stage_inputs_for_final, build_final_stage),
    PipelineStage("numbered", "Add printed page numbers to the full proceedings.", NUMBERED_PDF, stage_inputs_for_numbered, build_numbered_stage),
    PipelineStage("compressed", "Compress the numbered proceedings PDF.", COMPRESSED_PDF, stage_inputs_for_compression, build_compressed_stage),
]
