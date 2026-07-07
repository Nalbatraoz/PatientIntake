"""Frontend and uploads routes."""

import glob
import html
import json
import os
import re

from flask import Blueprint, Response, current_app, render_template, request, send_from_directory

from api.intake_completion import load_form_data, resolve_report_pdf_url
from api.utils import (
    FRONTEND_DIR,
    UPLOAD_DIR,
    build_ai_summary_points,
    format_answer,
    get_db_connection,
    password_required_response,
    read_storage_bytes,
    render_ai_report,
    storage_content_type,
    storage_file_exists,
    submissions_authorized,
)


form_bp = Blueprint("form", __name__)


def _send_frontend(filename):
    return send_from_directory(FRONTEND_DIR, filename)


def _maybe_json(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _normalize_submission_lookup(value):
    text = str(value or "").strip().upper()
    match = re.fullmatch(r"(?:INT[-\s]*)?(\d+)", text)
    if not match:
        return None
    submission_id = int(match.group(1))
    return submission_id if submission_id > 0 else None


def _report_chat_enabled(pipeline):
    report_agent_output = (pipeline or {}).get("report_agent") or {}
    return (
        str((pipeline or {}).get("status") or "").strip().lower() == "completed"
        and isinstance(report_agent_output, dict)
        and bool(report_agent_output.get("report"))
    )


def _report_chat_ai_html(pipeline):
    rendered = render_ai_report(pipeline)
    if str(rendered or "").strip():
        return rendered

    report = (
        ((pipeline or {}).get("report_agent") or {}).get("report")
        or (pipeline or {}).get("final_report")
        or {}
    )
    if not isinstance(report, dict) or not report:
        points = build_ai_summary_points(pipeline)
        if not points:
            return '<p class="ai-missing">No AI report available for this submission.</p>'
        items = "".join(f"<li>{html.escape(str(point))}</li>" for point in points)
        return f'<div class="ai-section"><div class="ai-section-title">AI Clinical Summary</div><div class="ai-list"><ul>{items}</ul></div></div>'

    def text(value):
        return html.escape(str(value or "").strip())

    def as_list(value):
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item or "").strip()]
        if str(value or "").strip():
            return [str(value).strip()]
        return []

    sections = []
    summary = (
        report.get("executive_summary")
        or report.get("clinical_summary")
        or report.get("summary")
        or ""
    )
    if summary:
        sections.append(
            '<div class="ai-section">'
            '<div class="ai-section-title">Final Report</div>'
            f'<div class="ai-summary-box"><p>{text(summary)}</p></div>'
            '</div>'
        )

    list_sections = [
        ("Findings", report.get("findings")),
        ("Urgent Safety Alerts", report.get("urgent_safety_alerts")),
        ("Clinical Findings", report.get("clinical_findings")),
        ("Medication Safety", report.get("medication_safety")),
        ("Evidence Summary", report.get("evidence_summary")),
        ("Clinician Actions", report.get("clinician_actions")),
        ("Missing Information", report.get("missing_information")),
        ("Limitations", report.get("limitations")),
        ("Citations", report.get("citations") or report.get("source_citations")),
    ]
    for title, values in list_sections:
        items = as_list(values)
        if not items:
            continue
        rows = "".join(f"<li>{html.escape(item)}</li>" for item in items)
        sections.append(
            '<div class="ai-section">'
            f'<div class="ai-section-title">{html.escape(title)}</div>'
            f'<div class="ai-list"><ul>{rows}</ul></div>'
            '</div>'
        )

    return "".join(sections) or '<p class="ai-missing">No AI report available for this submission.</p>'


def _resolve_uploaded_report_path(filename):
    normalized = os.path.normpath(filename).replace("\\", "/")
    if normalized.startswith("..") or os.path.isabs(normalized):
        return None

    if storage_file_exists(normalized):
        return normalized

    basename = os.path.basename(normalized)
    report_match = re.search(r"INT-[A-Za-z0-9_-]+", basename, re.IGNORECASE)
    if not report_match:
        return None

    code_token = report_match.group(0)
    patterns = [
        f"*{code_token}*.pdf",
        f"*({code_token}).pdf",
        f"*-{code_token}.pdf",
    ]
    for pattern in patterns:
        matches = sorted(glob.glob(os.path.join(UPLOAD_DIR, "reports", "**", pattern), recursive=True))
        if matches:
            return os.path.relpath(matches[0], UPLOAD_DIR).replace("\\", "/")
    return None


@form_bp.route("/")
def website():
    """Serve the main intake form page."""
    return _send_frontend("index.html")


@form_bp.route("/style.css")
def css():
    """Serve the frontend stylesheet."""
    return _send_frontend("style.css")


@form_bp.route("/script.js")
def js():
    """Serve the frontend JavaScript file."""
    return _send_frontend("script.js")


@form_bp.route("/notifications.js")
def notifications_js():
    return _send_frontend("notifications.js")


@form_bp.route("/notifications.css")
def notifications_css():
    return _send_frontend("notifications.css")


@form_bp.route("/nanovate-theme.css")
def nanovate_theme_css():
    """Serve the shared Nanovate dark theme overrides."""
    return _send_frontend("nanovate-theme.css")


@form_bp.route("/favicon.ico")
def favicon():
    """Avoid browser favicon 404 noise during local checks."""
    return Response(status=204)


@form_bp.route("/submissions.css")
def submissions_css():
    """Serve the submissions page stylesheet."""
    return _send_frontend("submissions.css")


@form_bp.route("/submissions.js")
def submissions_js():
    """Serve the submissions page JavaScript file."""
    return _send_frontend("submissions.js")


@form_bp.route("/report-chat.css")
def report_chat_css():
    """Serve the dedicated report chat page stylesheet."""
    return _send_frontend("report_chat.css")


@form_bp.route("/report-chat.js")
def report_chat_js():
    """Serve the dedicated report chat page JavaScript file."""
    return _send_frontend("report_chat.js")


@form_bp.route("/clinical-agent-test.css")
def clinical_agent_test_css():
    """Serve the clinical agent test page stylesheet."""
    return _send_frontend("clinical-agent-test.css")


@form_bp.route("/clinical-agent-test.js")
def clinical_agent_test_js():
    """Serve the clinical agent test page JavaScript."""
    return _send_frontend("clinical-agent-test.js")


@form_bp.route("/pedt")
def pedt_page():
    return _send_frontend("pedt.html")


@form_bp.route("/pedt.css")
def pedt_css():
    return _send_frontend("pedt.css")


@form_bp.route("/pedt.js")
def pedt_js():
    return _send_frontend("pedt.js")


@form_bp.route("/uploads/<path:filename>")
def uploaded_file(filename):
    """Serve a protected uploaded file after validating the requested path is safe."""
    normalized = os.path.normpath(filename).replace("\\", "/")
    if normalized.startswith("..") or os.path.isabs(normalized):
        return Response("Invalid upload path.", 400)

    is_report_pdf = normalized.startswith("reports/")
    if not is_report_pdf and not submissions_authorized():
        return password_required_response()

    resolved_path = normalized if not is_report_pdf else _resolve_uploaded_report_path(normalized)
    if not resolved_path or not storage_file_exists(resolved_path):
        return Response("Report PDF not found.", 404)

    response = Response(
        read_storage_bytes(resolved_path),
        mimetype=storage_content_type(resolved_path),
    )
    response.headers["Content-Disposition"] = f'inline; filename="{os.path.basename(resolved_path)}"'
    if is_report_pdf:
        response.headers["Cache-Control"] = "no-store, max-age=0"
    return response


@form_bp.route("/submissions")
def submissions():
    """Render a password-protected HTML page listing all submitted intake forms."""
    if not submissions_authorized():
        return password_required_response()

    conn = get_db_connection()
    rows = conn.execute(
        """
        SELECT id, full_name, age, mobile, email, form_data
        FROM intake_forms
        ORDER BY id DESC
        """
    ).fetchall()
    conn.close()

    submissions = []
    ignored_keys = {
        "clinical_pipeline",
        "completion",
        "iief_data",
        "pedt_data",
        "ehs_data",
        "low_libido_data",
        "uploadedFiles",
        "uploadedDrugAnalysis",
        "uploadedFileSummary",
    }

    for row in rows:
        form_data = load_form_data(row["form_data"])
        pipeline = form_data.pop("clinical_pipeline", None)
        iief_data = form_data.pop("iief_data", None)
        pedt_data = form_data.pop("pedt_data", None)
        ehs_data = form_data.pop("ehs_data", None)
        low_libido_data = form_data.pop("low_libido_data", None)
        report_pdf = (pipeline or {}).get("report_pdf") or {}
        uploaded_files = _maybe_json(form_data.pop("uploadedFiles", None))
        uploaded_drug_analysis = _maybe_json(form_data.pop("uploadedDrugAnalysis", None))
        uploaded_file_summary = _maybe_json(form_data.pop("uploadedFileSummary", None))
        submission_id = row["id"]
        code_no = f"INT-{submission_id}"
        report_chat_enabled = _report_chat_enabled(pipeline)

        submissions.append({
            "id": submission_id,
            "full_name": row["full_name"] or "",
            "age": row["age"] or "",
            "mobile": row["mobile"] or "",
            "email": row["email"] or "",
            "code_no": code_no,
            "form_panel_id": f"form-panel-{submission_id}",
            "ai_panel_id": f"ai-panel-{submission_id}",
            "ai_summary_panel_id": f"ai-summary-panel-{submission_id}",
            "report_chat_panel_id": f"report-chat-panel-{submission_id}",
            "report_chat_enabled": report_chat_enabled,
            "upload_panel_id": f"upload-panel-{submission_id}",
            "iief_panel_id": f"iief-panel-{submission_id}",
            "pedt_panel_id": f"pedt-panel-{submission_id}",
            "ehs_panel_id": f"ehs-panel-{submission_id}",
            "low_libido_panel_id": f"low-libido-panel-{submission_id}",
            "report_pdf_url": resolve_report_pdf_url(report_pdf, code_no),
            "report_pdf_error": report_pdf.get("error"),
            "uploaded_files": uploaded_files,
            "uploaded_drug_analysis": uploaded_drug_analysis,
            "uploaded_file_summary": uploaded_file_summary,
            "ai_summary_points": build_ai_summary_points(pipeline),
            "iief_data": iief_data,
            "pedt_data": pedt_data,
            "ehs_data": ehs_data,
            "low_libido_data": low_libido_data,
            "answers": [
                {"key": str(key), "value": format_answer(value)}
                for key, value in form_data.items()
                if key not in ignored_keys
            ],
            "ai_html": render_ai_report(pipeline),
        })

    return render_template("submissions.html", submissions=submissions)


@form_bp.get("/report-chat")
def report_chat_page():
    """Render the dedicated report chat page for one completed report."""
    if not submissions_authorized():
        return password_required_response()

    requested_id = (
        request.args.get("submission_id")
        or request.args.get("codeNo")
        or request.args.get("code_no")
    )
    submission_id = _normalize_submission_lookup(requested_id)
    if not submission_id:
        return Response("submission_id must be a number or code like INT-1.", 400)

    conn = get_db_connection()
    try:
        row = conn.execute(
            """
            SELECT id, full_name, age, mobile, email, form_data
            FROM intake_forms
            WHERE id = ?
            """,
            (submission_id,),
        ).fetchone()
    finally:
        conn.close()

    if not row:
        return Response(f"Submission INT-{submission_id} was not found.", 404)

    form_data = load_form_data(row["form_data"])
    pipeline = form_data.get("clinical_pipeline") or {}
    if not _report_chat_enabled(pipeline):
        return Response("Report chat is available only after a final report is generated.", 409)

    code_no = f"INT-{row['id']}"
    report_pdf = pipeline.get("report_pdf") or {}
    submission = {
        "id": int(row["id"]),
        "full_name": row["full_name"] or "",
        "age": row["age"] or "",
        "mobile": row["mobile"] or "",
        "email": row["email"] or "",
        "code_no": code_no,
        "report_pdf_url": resolve_report_pdf_url(report_pdf, code_no),
        "ai_summary_points": build_ai_summary_points(pipeline),
        "ai_html": _report_chat_ai_html(pipeline),
    }

    current_app.jinja_env.cache.clear()
    return render_template("report_chat.html", submission=submission)
