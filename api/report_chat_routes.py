"""Report-specific chat routes for completed submissions."""

from flask import Blueprint, jsonify, request

import nodes.agents as report_chat_agent_module
from api.utils import (
    GEMINI_REPORT_CHAT_MODEL,
    deployment_info,
    list_report_chat_history,
    password_required_response,
    report_chat_dependencies,
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
