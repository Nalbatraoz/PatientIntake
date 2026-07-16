"""Report-specific chat routes for completed submissions."""

from flask import Blueprint, jsonify, request

import nodes.agents as report_chat_agent_module
from api.intake_completion import resolve_report_pdf_url
from api.utils import (
    GEMINI_REPORT_CHAT_MODEL,
    GEMINI_REPORT_PATCH_MODEL,
    build_ai_summary_points,
    deployment_info,
    list_report_chat_history,
    password_required_response,
    render_ai_report,
    report_chat_dependencies,
    save_doctor_report_note,
    save_report_patch_result,
    save_report_chat_message,
    submissions_authorized,
)


report_chat_bp = Blueprint("report_chat", __name__)


def _request_submission_id(payload=None):
    payload = payload or {}
    return (
        payload.get("submission_id")
        or payload.get("codeNo")
        or payload.get("code_no")
        or request.args.get("submission_id")
        or request.args.get("codeNo")
        or request.args.get("code_no")
    )


def _status_for_error(exc):
    if isinstance(exc, report_chat_agent_module.ReportChatError):
        return 400
    if isinstance(exc, report_chat_agent_module.ReportChatNotFound):
        return 404
    if isinstance(exc, report_chat_agent_module.ReportChatUnavailable):
        return 409
    return 500


def _json_error(message, status):
    return jsonify({"error": message}), status


def _assert_completed_report_available(submission_id):
    submission = report_chat_agent_module.load_report_chat_submission(
        submission_id,
        get_db_connection=report_chat_dependencies()["get_db_connection"],
        safe_json_loads=report_chat_dependencies()["safe_json_loads"],
    )
    report_chat_agent_module.build_report_chat_packet(
        submission,
        "Return chat history availability for this completed report.",
    )
    return submission


@report_chat_bp.get("/report-chat/history")
def report_chat_history():
    """Return saved chat messages for one completed report."""
    if not submissions_authorized():
        return password_required_response()

    try:
        submission_id = report_chat_agent_module.normalize_submission_id(_request_submission_id())
        _assert_completed_report_available(submission_id)
    except (
        report_chat_agent_module.ReportChatError,
        report_chat_agent_module.ReportChatNotFound,
        report_chat_agent_module.ReportChatUnavailable,
    ) as exc:
        return _json_error(str(exc), _status_for_error(exc))

    return jsonify({
        "submission_id": submission_id,
        "codeNo": f"INT-{submission_id}",
        "history": list_report_chat_history(submission_id),
    })


@report_chat_bp.post("/report-chat")
def report_chat():
    """Answer a doctor question about one completed generated report."""
    if not submissions_authorized():
        return password_required_response()

    payload = request.get_json(silent=True) or {}
    try:
        submission_id = report_chat_agent_module.normalize_submission_id(_request_submission_id(payload))
        question = str(payload.get("question") or "").strip()
        result = report_chat_agent_module.run_report_chat_agent(
            submission_id,
            question,
            report_chat_dependencies(),
            model_name=GEMINI_REPORT_CHAT_MODEL,
        )
    except (
        report_chat_agent_module.ReportChatError,
        report_chat_agent_module.ReportChatNotFound,
        report_chat_agent_module.ReportChatUnavailable,
    ) as exc:
        return _json_error(str(exc), _status_for_error(exc))

    saved = save_report_chat_message(
        result["submission_id"],
        result["question"],
        result["answer"],
        model=result.get("model") or "",
        context_hash=result.get("context_hash") or "",
    )
    return jsonify({
        "submission_id": result["submission_id"],
        "codeNo": result["code_no"],
        "question": result["question"],
        "answer": result["answer"],
        "chat_id": saved["id"],
        "created_at": saved["created_at"],
        "model": result.get("model") or "",
        "engine": result.get("engine") or "crewai",
        "context_hash": result.get("context_hash") or "",
        "error": result.get("error"),
        "deployment": deployment_info(),
    })


@report_chat_bp.post("/report-chat/report-edit")
def report_chat_report_edit():
    """Save a clinician-edited structured final report and regenerate its PDF."""
    if not submissions_authorized():
        return password_required_response()
    payload = request.get_json(silent=True) or {}
    try:
        submission_id = report_chat_agent_module.normalize_submission_id(_request_submission_id(payload))
        _assert_completed_report_available(submission_id)
        report = payload.get("report")
        if not isinstance(report, dict) or not report:
            return _json_error("report must be a non-empty JSON object.", 400)
        saved = save_report_patch_result(
            submission_id, report,
            filled_information="Clinician manual report edit",
            engine="manual",
        )
    except (report_chat_agent_module.ReportChatError,
            report_chat_agent_module.ReportChatNotFound,
            report_chat_agent_module.ReportChatUnavailable) as exc:
        return _json_error(str(exc), _status_for_error(exc))
    except LookupError as exc:
        return _json_error(str(exc), 404)
    report_pdf = saved.get("report_pdf") or {}
    return jsonify({
        "submission_id": submission_id,
        "codeNo": saved["code_no"],
        "report": saved["report"],
        "patch_entry": saved["patch_entry"],
        "ai_html": render_ai_report(saved["pipeline"]),
        "ai_summary_points": build_ai_summary_points(saved["pipeline"]),
        "report_pdf_url": resolve_report_pdf_url(report_pdf, saved["code_no"]),
        "report_pdf_error": report_pdf.get("error"),
        "deployment": deployment_info(),
    })


@report_chat_bp.post("/report-chat/doctor-note")
def report_chat_doctor_note():
    """Add a doctor-authored note to the selected report's saved context."""
    if not submissions_authorized():
        return password_required_response()

    payload = request.get_json(silent=True) or {}
    try:
        submission_id = report_chat_agent_module.normalize_submission_id(_request_submission_id(payload))
        _assert_completed_report_available(submission_id)
        note_text = str(payload.get("note") or payload.get("text") or "").strip()
        saved = save_doctor_report_note(submission_id, note_text)
    except (
        report_chat_agent_module.ReportChatError,
        report_chat_agent_module.ReportChatNotFound,
        report_chat_agent_module.ReportChatUnavailable,
    ) as exc:
        return _json_error(str(exc), _status_for_error(exc))
    except (ValueError, LookupError) as exc:
        return _json_error(str(exc), 400 if isinstance(exc, ValueError) else 404)

    return jsonify({
        "submission_id": saved["submission_id"],
        "codeNo": saved["code_no"],
        "note": saved["note"],
        "deployment": deployment_info(),
    })


@report_chat_bp.post("/report-chat/report-patch")
def report_chat_report_patch():
    """Patch the saved final report with doctor-supplied missing information."""
    if not submissions_authorized():
        return password_required_response()

    payload = request.get_json(silent=True) or {}
    try:
        submission_id = report_chat_agent_module.normalize_submission_id(_request_submission_id(payload))
        filled_information = str(
            payload.get("filled_information")
            or payload.get("note")
            or payload.get("text")
            or ""
        ).strip()
        missing_item = str(payload.get("missing_item") or "").strip()
        result = report_chat_agent_module.run_report_patch_agent(
            submission_id,
            filled_information,
            report_chat_dependencies(),
            missing_item=missing_item,
            model_name=GEMINI_REPORT_PATCH_MODEL,
        )
        saved = save_report_patch_result(
            result["submission_id"],
            result["patched_report"],
            filled_information=result["filled_information"],
            model=result.get("model") or "",
            engine=result.get("engine") or "crewai",
            error=result.get("error") or "",
        )
    except (
        report_chat_agent_module.ReportChatError,
        report_chat_agent_module.ReportChatNotFound,
        report_chat_agent_module.ReportChatUnavailable,
    ) as exc:
        return _json_error(str(exc), _status_for_error(exc))
    except LookupError as exc:
        return _json_error(str(exc), 404)

    code_no = saved["code_no"]
    report_pdf = saved.get("report_pdf") or {}
    return jsonify({
        "submission_id": result["submission_id"],
        "codeNo": code_no,
        "filled_information": result["filled_information"],
        "report": saved["report"],
        "missing_information_before": result.get("missing_information_before") or [],
        "missing_information_after": result.get("missing_information_after") or [],
        "patch_entry": saved["patch_entry"],
        "ai_html": render_ai_report(saved["pipeline"]),
        "ai_summary_points": build_ai_summary_points(saved["pipeline"]),
        "report_pdf_url": resolve_report_pdf_url(report_pdf, code_no),
        "report_pdf_error": report_pdf.get("error"),
        "model": result.get("model") or "",
        "engine": result.get("engine") or "crewai",
        "error": result.get("error"),
        "deployment": deployment_info(),
    })
