"""Shared intake completion helpers and notification state."""

import glob
import json
import os
import threading
import time

from api.utils import APP_BASE_PATH, UPLOAD_DIR, storage_file_exists


_notification_lock = threading.Lock()
_notification_listeners = []

_COMPLAINT_TO_FORM_KEY = {
    "low_libido": "low_libido_data",
    "premature_ejaculation": "pedt_data",
    "erectile_dysfunction": "ehs_data",
}

# The patient completes the main intake plus IIEF. PEDT, EHS, and Low Libido are
# doctor questionnaires filled later from the submissions page, so they no longer
# gate intake completion or the new-submission notification.
_REQUIRED_BASE_FORM_KEYS = ("iief_data",)


def broadcast_notification(payload):
    """Send a submission event to every connected SSE listener."""
    data = json.dumps(payload, ensure_ascii=False)
    with _notification_lock:
        dead = []
        for q in _notification_listeners:
            try:
                q.put_nowait(data)
            except Exception:
                dead.append(q)
        for q in dead:
            _notification_listeners.remove(q)


def load_form_data(raw_value):
    """Parse persisted form JSON safely."""
    try:
        return json.loads(raw_value or "{}")
    except json.JSONDecodeError:
        return {}


def extract_complaints(form_data):
    """Return the patient complaint list as normalized strings."""
    complaints = form_data.get("complaints", [])
    if isinstance(complaints, str):
        complaints = [item.strip() for item in complaints.split(",")]
    if not isinstance(complaints, list):
        return []
    return [str(item).strip() for item in complaints if str(item).strip()]


def required_form_keys(form_data):
    """Return the patient questionnaire keys needed before the intake is complete."""
    return set(_REQUIRED_BASE_FORM_KEYS)


def recommended_doctor_form_keys(form_data):
    """Return the doctor questionnaire keys suggested by the patient's complaints."""
    recommended = set()
    for complaint in extract_complaints(form_data):
        form_key = _COMPLAINT_TO_FORM_KEY.get(complaint)
        if form_key:
            recommended.add(form_key)
    return recommended


def form_completion_state(form_data):
    """Compute which patient questionnaire sections are complete."""
    required = sorted(required_form_keys(form_data))
    completed = sorted(key for key in required if form_data.get(key))
    completion = form_data.get("completion") if isinstance(form_data.get("completion"), dict) else {}
    return {
        "required_forms": required,
        "completed_forms": completed,
        "is_complete": len(completed) == len(required),
        "notified": bool(completion.get("notified")),
        "completed_at": completion.get("completed_at"),
    }


def persist_completion_state(conn, submission_id, form_data, completion_state, notify_payload=None):
    """Store completion status and send a single notification when the intake is finished."""
    updated_completion = dict(completion_state)
    should_notify = updated_completion["is_complete"] and not updated_completion["notified"]
    if should_notify:
        updated_completion["notified"] = True
        updated_completion["completed_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")

    form_data["completion"] = updated_completion
    conn.execute(
        "UPDATE intake_forms SET form_data = ? WHERE id = ?",
        (json.dumps(form_data, ensure_ascii=False), submission_id),
    )
    conn.commit()

    if should_notify:
        notify_payload = notify_payload or {}
        broadcast_notification({
            "type": "new_submission",
            "submission_id": submission_id,
            "full_name": notify_payload.get("full_name") or "",
            "visit_type": notify_payload.get("visit_type") or "",
            "age": str(notify_payload.get("age") or ""),
            "codeNo": f"INT-{submission_id}",
            "timestamp": time.strftime("%H:%M"),
        })

    return updated_completion


def public_upload_url(relative_path):
    """Build a public uploads URL that respects any reverse-proxy path prefix."""
    relative_path = str(relative_path or "").replace("\\", "/").lstrip("/")
    prefix = APP_BASE_PATH.rstrip("/")
    if prefix:
        return f"{prefix}/uploads/{relative_path}"
    return f"/uploads/{relative_path}"


def resolve_report_pdf_url(report_pdf, code_no):
    """Return a report PDF URL only when a real file exists in configured storage."""
    report_pdf = report_pdf or {}
    candidate_paths = []

    relative_path = str(report_pdf.get("relative_path") or "").strip().replace("\\", "/").lstrip("/")
    if relative_path:
        candidate_paths.append(relative_path)

    url = str(report_pdf.get("url") or "").strip()
    if url.startswith("/uploads/"):
        candidate_paths.append(url.removeprefix("/uploads/"))
    if APP_BASE_PATH and url.startswith(f"{APP_BASE_PATH}/uploads/"):
        candidate_paths.append(url.removeprefix(f"{APP_BASE_PATH}/uploads/"))

    for relative in candidate_paths:
        if storage_file_exists(relative):
            return public_upload_url(relative)

    code_token = str(code_no or "").strip()
    if not code_token:
        return None

    patterns = [
        f"*{code_token}*.pdf",
        f"*({code_token}).pdf",
        f"*-{code_token}.pdf",
    ]
    for pattern in patterns:
        matches = sorted(glob.glob(os.path.join(UPLOAD_DIR, "reports", "**", pattern), recursive=True))
        if matches:
            relative = os.path.relpath(matches[0], UPLOAD_DIR).replace("\\", "/")
            return public_upload_url(relative)

    return None

