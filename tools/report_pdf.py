"""PDF rendering helpers for the final report agent."""

import os
import re
import shutil
import textwrap
from datetime import datetime

from tools.report_normalization import canonical_report_sections, dedupe_list, normalize_final_report


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_BASE_PATH = os.environ.get("APP_BASE_PATH", "").strip()
if APP_BASE_PATH and APP_BASE_PATH != "/":
    APP_BASE_PATH = "/" + APP_BASE_PATH.strip("/")
else:
    APP_BASE_PATH = ""


def public_upload_url(relative_path):
    """Build a public uploads URL that respects any reverse-proxy path prefix."""
    relative_path = str(relative_path or "").replace("\\", "/").lstrip("/")
    prefix = APP_BASE_PATH.rstrip("/")
    if prefix:
        return f"{prefix}/uploads/{relative_path}"
    return f"/uploads/{relative_path}"


def _pdf_escape(text):
    """Escape a text string for a simple PDF content stream."""
    text = str(text or "")
    text = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return text.encode("cp1252", "replace").decode("cp1252")


def _clean_pdf_text(text):
    """Normalize whitespace and characters unsupported by the built-in PDF font."""
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    return text.encode("cp1252", "replace").decode("cp1252")


def _clean_unicode_text(text):
    """Normalize whitespace while preserving Unicode text for Arabic PDFs."""
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _add_wrapped_rows(rows, style, text, *, width=88, prefix=""):
    """Append wrapped styled rows while preserving indentation for continuation lines."""
    cleaned = _clean_pdf_text(text)
    if not cleaned:
        return
    initial_indent = prefix
    subsequent_indent = " " * len(prefix)
    wrapped = textwrap.wrap(
        cleaned,
        width=width,
        initial_indent=initial_indent,
        subsequent_indent=subsequent_indent,
    ) or [prefix]
    rows.extend({"style": style, "text": line} for line in wrapped)


def _report_lines(report):
    """Flatten structured report JSON into styled rows for the PDF writer."""
    report = normalize_final_report(report)
    rows = []
    title_parts = textwrap.wrap(
        _clean_pdf_text(report.get("report_title") or "AI Clinical Evidence Report"),
        width=58,
    ) or ["AI Clinical Evidence Report"]
    rows.append({"style": "title", "text": title_parts[0]})
    rows.extend({"style": "title_cont", "text": part} for part in title_parts[1:])
    rows.extend([
        {"style": "meta", "text": f"Generated: {datetime.utcnow().isoformat(timespec='seconds')}Z"},
        {"style": "spacer", "text": ""},
    ])
    snapshot = report.get("patient_snapshot") or {}
    snapshot_parts = [
        f"Submission ID: {snapshot.get('submission_id', '')}",
        f"Age: {snapshot.get('age', '')}",
        f"Sex: {snapshot.get('sex', '')}",
    ]
    rows.append({"style": "section", "text": "Patient Snapshot"})
    for part in snapshot_parts:
        _add_wrapped_rows(rows, "body", part, width=84)
    rows.append({"style": "spacer", "text": ""})

    summary = report.get("clinical_summary") or report.get("executive_summary") or ""
    if summary:
        rows.append({"style": "section", "text": "Clinical Summary"})
        _add_wrapped_rows(rows, "body", summary, width=82)
        rows.append({"style": "spacer", "text": ""})

    for heading, items in _iter_report_sections(report):
        rows.append({"style": "section", "text": heading})
        for item in items:
            _add_wrapped_rows(rows, "item", item, width=82, prefix="- ")
        rows.append({"style": "spacer", "text": ""})

    citations = dedupe_list(report.get("citations") or report.get("source_citations"))
    if citations:
        rows.append({"style": "section", "text": "Citations"})
        for item in citations:
            _add_wrapped_rows(rows, "item", item, width=82, prefix="- ")
        rows.append({"style": "spacer", "text": ""})
    return rows


PDF_STYLES = {
    "title": {"font": "F2", "size": 17, "height": 24, "color": (0.10, 0.27, 0.43)},
    "title_cont": {"font": "F2", "size": 15, "height": 21, "color": (0.10, 0.27, 0.43)},
    "section": {"font": "F2", "size": 12, "height": 25, "color": (0.10, 0.27, 0.43), "section_band": True},
    "meta": {"font": "F1", "size": 9, "height": 13, "color": (0.34, 0.40, 0.47)},
    "item": {"font": "F1", "size": 9.5, "height": 14, "color": (0.10, 0.13, 0.20)},
    "body": {"font": "F1", "size": 9.5, "height": 14, "color": (0.10, 0.13, 0.20)},
    "muted": {"font": "F1", "size": 10, "height": 14, "color": (0.42, 0.45, 0.50)},
    "spacer": {"font": "F1", "size": 4, "height": 10, "color": (1, 1, 1)},
}


def _pdf_text_command(row, x, y):
    """Return PDF drawing commands for one styled row."""
    style = PDF_STYLES.get(row.get("style"), PDF_STYLES["body"])
    text = _pdf_escape(row.get("text", ""))
    r, g, b = style["color"]
    commands = []
    if style.get("section_band"):
        commands.append("0.91 0.95 0.99 rg")
        commands.append(f"{x - 10} {y - 6} 502 21 re f")
        commands.append("0.12 0.31 0.47 rg")
        commands.append(f"{x - 10} {y - 6} 4 21 re f")
    commands.extend([
        f"{r} {g} {b} rg",
        "BT",
        f"/{style['font']} {style['size']} Tf",
        f"{x + (5 if style.get('section_band') else 0)} {y} Td",
        f"({text}) Tj",
        "ET",
    ])
    return commands


def _pdf_page_stream(rows):
    """Paginate styled rows into PDF page content streams."""
    pages = []
    page_commands = []
    margin_x = 50
    y = 710

    def start_page(page_index):
        commands = [
            "0.95 0.97 0.99 rg",
            "0 0 612 792 re f",
            "1 1 1 rg",
            "38 38 536 706 re f",
        ]
        if page_index == 0:
            commands.extend([
                "0.12 0.31 0.47 rg",
                "38 730 536 7 re f",
                "0.84 0.90 0.96 rg",
                "38 724 536 1 re f",
            ])
        return commands

    page_index = 0
    page_commands = start_page(page_index)
    for row in rows:
        style = PDF_STYLES.get(row.get("style"), PDF_STYLES["body"])
        if y - style["height"] < 56:
            pages.append(page_commands)
            page_index += 1
            page_commands = start_page(page_index)
            y = 710
        if row.get("style") != "spacer":
            page_commands.extend(_pdf_text_command(row, margin_x, y))
        y -= style["height"]

    pages.append(page_commands)
    return ["\n".join(commands).encode("cp1252", "replace") for commands in pages]


def write_simple_pdf(rows, output_path):
    """Write a styled text PDF using only the Python standard library."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    if rows and isinstance(rows[0], str):
        rows = [{"style": "body", "text": line} for line in rows]

    objects = []

    def add_object(payload):
        objects.append(payload)
        return len(objects)

    font_id = add_object(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    bold_font_id = add_object(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")
    page_ids = []
    content_ids = []
    page_streams = _pdf_page_stream(rows or [])

    for stream in page_streams:
        content_id = add_object(
            b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream"
        )
        content_ids.append(content_id)
        page_ids.append(None)

    pages_id = len(objects) + len(content_ids) + 1
    for index, content_id in enumerate(content_ids):
        page_ids[index] = add_object(
            (
                f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 612 792] "
                f"/Resources << /Font << /F1 {font_id} 0 R /F2 {bold_font_id} 0 R >> >> "
                f"/Contents {content_id} 0 R >>"
            ).encode("ascii")
        )

    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    pages_payload = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode("ascii")
    actual_pages_id = add_object(pages_payload)
    catalog_id = add_object(f"<< /Type /Catalog /Pages {actual_pages_id} 0 R >>".encode("ascii"))

    pdf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for object_id, payload in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{object_id} 0 obj\n".encode("ascii"))
        pdf.extend(payload)
        pdf.extend(b"\nendobj\n")

    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )

    with open(output_path, "wb") as file_obj:
        file_obj.write(pdf)


def _load_arabic_pdf_libs():
    """Load Arabic PDF dependencies only when Arabic PDF generation is requested."""
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.pdfgen import canvas
    except ImportError as exc:
        raise RuntimeError(
            "Arabic PDF generation requires reportlab, arabic-reshaper, and python-bidi."
        ) from exc
    return arabic_reshaper, get_display, colors, letter, pdfmetrics, TTFont, canvas


def _arabic_font_paths():
    """Return regular/bold Arabic-capable font paths for Windows or Linux hosts."""
    fonts_dir = os.environ.get("ARABIC_PDF_FONTS_DIR")
    candidates = []

    local_fonts_dir = os.path.join(BASE_DIR, "fonts")
    candidate_dirs = [d for d in (fonts_dir, local_fonts_dir) if d]

    for base_dir in candidate_dirs:
        candidates.extend([
            (os.path.join(base_dir, "Arabic-Regular.ttf"), os.path.join(base_dir, "Arabic-Bold.ttf")),
            (os.path.join(base_dir, "NotoNaskhArabic-Regular.ttf"), os.path.join(base_dir, "NotoNaskhArabic-Bold.ttf")),
            (os.path.join(base_dir, "NotoSansArabic-Regular.ttf"), os.path.join(base_dir, "NotoSansArabic-Bold.ttf")),
            (os.path.join(base_dir, "Amiri-Regular.ttf"), os.path.join(base_dir, "Amiri-Bold.ttf")),
            (os.path.join(base_dir, "DejaVuSans.ttf"), os.path.join(base_dir, "DejaVuSans-Bold.ttf")),
            (os.path.join(base_dir, "LiberationSans-Regular.ttf"), os.path.join(base_dir, "LiberationSans-Bold.ttf")),
        ])

    candidates.extend([
        (r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\arialbd.ttf"),
        (r"C:\Windows\Fonts\tahoma.ttf", r"C:\Windows\Fonts\tahomabd.ttf"),
        (r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\segoeuib.ttf"),
        ("/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf", "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Bold.ttf"),
        ("/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf", "/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf"),
        ("/usr/share/fonts/truetype/amiri/Amiri-Regular.ttf", "/usr/share/fonts/truetype/amiri/Amiri-Bold.ttf"),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf", "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"),
    ])

    for regular, bold in candidates:
        if os.path.exists(regular) and os.path.exists(bold):
            return regular, bold
    raise RuntimeError(
        "No Arabic-capable font was found. Set ARABIC_PDF_FONTS_DIR or install "
        "Noto Naskh Arabic, Amiri, DejaVu Sans, or Liberation Sans."
    )


def _shape_arabic(text, arabic_reshaper, get_display):
    """Shape Arabic text for drawing with a PDF canvas."""
    text = _clean_unicode_text(text)
    return get_display(arabic_reshaper.reshape(text))


def _arabic_font_status():
    """Return the resolved Arabic font file paths used by the PDF writer."""
    regular_font, bold_font = _arabic_font_paths()
    return {
        "regular": regular_font,
        "bold": bold_font,
        "regular_exists": os.path.exists(regular_font),
        "bold_exists": os.path.exists(bold_font),
    }


def _arabic_wrapped_lines(text, width=72, prefix=""):
    """Wrap Arabic text before bidi shaping."""
    cleaned = _clean_unicode_text(text)
    if not cleaned:
        return []
    return textwrap.wrap(
        cleaned,
        width=width,
        initial_indent=prefix,
        subsequent_indent=" " * len(prefix),
    ) or [prefix]


def _iter_report_sections(report):
    """Yield canonical report sections as ``(heading, items)`` pairs."""
    for section in canonical_report_sections(report):
        if isinstance(section, dict):
            heading = str(section.get("heading") or "").strip()
            items = section.get("items") or []
        elif isinstance(section, (list, tuple)) and len(section) == 2:
            heading, items = section
            heading = str(heading or "").strip()
        else:
            continue
        if heading:
            yield heading, items


def _arabic_sections(report):
    """Return Arabic PDF sections from an Arabic structured report."""
    report = normalize_final_report(report)
    snapshot = report.get("patient_snapshot") or {}
    arabic_titles = {
        "Urgent Safety Alerts": "تنبيهات السلامة العاجلة",
        "Medication Safety": "سلامة الأدوية",
        "Findings": "النتائج",
        "Clinical Findings": "النتائج السريرية",
        "Evidence Summary": "ملخص الأدلة",
        "Clinician Actions": "إجراءات مقترحة للطبيب",
        "Missing Information": "المعلومات الناقصة",
        "Limitations": "القيود",
        "Citations": "المراجع والاستشهادات",
        "Clinical Summary": "الملخص السريري",
    }

    sections = [
        ("بيانات المريض", [
            f"رقم الملف: {snapshot.get('submission_id', '')}",
            f"العمر: {snapshot.get('age', '')}",
            f"النوع: {snapshot.get('sex', '')}",
        ]),
    ]

    summary = report.get("clinical_summary") or report.get("executive_summary") or ""
    if summary:
        sections.append(("الملخص السريري", [summary]))

    for heading, items in _iter_report_sections(report):
        sections.append((arabic_titles.get(heading, heading), items))

    citations = dedupe_list(report.get("citations") or report.get("source_citations"))
    if citations:
        sections.append(("المراجع والاستشهادات", citations))

    return sections


def write_arabic_pdf(report, output_path, *, font_paths=None):
    """Write an Arabic RTL PDF using ReportLab with embedded Arabic fonts."""
    report = normalize_final_report(report)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    arabic_reshaper, get_display, colors, letter, pdfmetrics, TTFont, canvas = _load_arabic_pdf_libs()
    regular_font, bold_font = font_paths or _arabic_font_paths()
    pdfmetrics.registerFont(TTFont("ArabicRegular", regular_font))
    pdfmetrics.registerFont(TTFont("ArabicBold", bold_font))

    page_width, page_height = letter
    pdf = canvas.Canvas(output_path, pagesize=letter)
    left = 44
    right = page_width - 50
    y = page_height - 82
    page_index = 0

    def draw_page_background():
        pdf.setFillColor(colors.HexColor("#f2f6fb"))
        pdf.rect(0, 0, page_width, page_height, stroke=0, fill=1)
        pdf.setFillColor(colors.white)
        pdf.rect(38, 38, page_width - 76, page_height - 86, stroke=0, fill=1)
        if page_index == 0:
            pdf.setFillColor(colors.HexColor("#1f4e79"))
            pdf.rect(38, page_height - 60, page_width - 76, 7, stroke=0, fill=1)
            pdf.setFillColor(colors.HexColor("#d5e3f2"))
            pdf.rect(38, page_height - 66, page_width - 76, 1, stroke=0, fill=1)

    def new_page():
        nonlocal y, page_index
        pdf.showPage()
        page_index += 1
        draw_page_background()
        y = page_height - 92

    def ensure_space(height):
        if y - height < 58:
            new_page()

    def draw_rtl_line(text, *, font="ArabicRegular", size=10, color="#172033", x=None):
        nonlocal y
        if not text:
            return
        pdf.setFont(font, size)
        pdf.setFillColor(colors.HexColor(color))
        pdf.drawRightString(x or right, y, _shape_arabic(text, arabic_reshaper, get_display))

    def draw_rtl_meta(label, value, *, font="ArabicRegular", size=9, color="#56677a", gap=8):
        """Draw an Arabic label with an adjacent LTR metadata value."""
        value = str(value or "").strip()
        if not label and not value:
            return
        shaped_label = _shape_arabic(label, arabic_reshaper, get_display)
        pdf.setFont(font, size)
        pdf.setFillColor(colors.HexColor(color))
        pdf.drawRightString(right, y, shaped_label)
        if value:
            label_width = pdf.stringWidth(shaped_label, font, size)
            value_width = pdf.stringWidth(value, font, size)
            value_x = max(left, right - label_width - gap - value_width)
            pdf.drawString(value_x, y, value)

    def draw_wrapped(text, *, prefix="", font="ArabicRegular", size=10, color="#172033", width=74):
        nonlocal y
        for line in _arabic_wrapped_lines(text, width=width, prefix=prefix):
            ensure_space(16)
            draw_rtl_line(line, font=font, size=size, color=color)
            y -= 15

    def draw_section(title):
        nonlocal y
        ensure_space(34)
        pdf.setFillColor(colors.HexColor("#e8f2fb"))
        pdf.rect(left, y - 9, right - left, 24, stroke=0, fill=1)
        pdf.setFillColor(colors.HexColor("#1f4e79"))
        pdf.rect(right - 4, y - 9, 4, 24, stroke=0, fill=1)
        draw_rtl_line(title, font="ArabicBold", size=12, color="#1f4e79", x=right - 12)
        y -= 32

    draw_page_background()
    title_lines = _arabic_wrapped_lines(report.get("report_title") or "تقرير المراجعة السريرية", width=46)
    for index, line in enumerate(title_lines):
        ensure_space(24)
        draw_rtl_line(line, font="ArabicBold", size=17 if index == 0 else 15, color="#1f4e79")
        y -= 24 if index == 0 else 20

    draw_rtl_meta(
        "تاريخ الإصدار:",
        datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        size=9,
        color="#56677a",
    )
    y -= 24

    for heading, items in _arabic_sections(report):
        draw_section(heading)
        normalized = dedupe_list(items)
        if not normalized:
            draw_wrapped("لا توجد عناصر مسجلة.", font="ArabicRegular", size=10, color="#6b7280")
        for item in normalized:
            draw_wrapped(item, prefix="- ", font="ArabicRegular", size=10, width=72)
        y -= 10

    pdf.save()


def save_report_pdf(report, *, upload_dir, submission_id=None, patient_name=None, code_no=None, arabic=False):
    """Save the structured report as a PDF under uploads/reports and return metadata."""
    date_folder = datetime.utcnow().strftime("%Y%m%d")
    fallback_id = str(submission_id or "unsaved")
    safe_code = re.sub(r"[^A-Za-z0-9_-]+", "-", str(code_no or "").strip()).strip("-")
    safe_id = re.sub(r"[^A-Za-z0-9_-]+", "-", fallback_id).strip("-")
    safe_patient_name = re.sub(r"[^A-Za-z0-9_-]+", "-", str(patient_name or "").strip()).strip("-")
    if safe_code:
        filename_base = f"clinical-report-{safe_code}"
    else:
        filename_base = f"clinical-report-{safe_id}"

    filename = f"{filename_base}.pdf"
    relative_path = os.path.join("reports", date_folder, filename)
    absolute_path = os.path.join(upload_dir, relative_path)
    font_status = None
    if arabic:
        font_status = _arabic_font_status()
        write_arabic_pdf(report or {}, absolute_path, font_paths=(font_status["regular"], font_status["bold"]))
    else:
        write_simple_pdf(_report_lines(report or {}), absolute_path)

    legacy_filename = ""
    if safe_patient_name and safe_code:
        legacy_filename = f"{safe_patient_name}-({safe_code}).pdf"
    elif safe_code:
        legacy_filename = f"clinical-report-({safe_code}).pdf"
    elif safe_patient_name:
        legacy_filename = f"{safe_patient_name}.pdf"

    if legacy_filename and legacy_filename != filename:
        legacy_relative_path = os.path.join("reports", date_folder, legacy_filename)
        legacy_absolute_path = os.path.join(upload_dir, legacy_relative_path)
        os.makedirs(os.path.dirname(legacy_absolute_path), exist_ok=True)
        shutil.copyfile(absolute_path, legacy_absolute_path)

    return {
        "relative_path": relative_path.replace(os.sep, "/"),
        "url": public_upload_url(relative_path),
        "filename": filename,
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "font_status": font_status,
    }
