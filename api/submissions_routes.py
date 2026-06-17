"""Intake submission and completion routes."""

import json
import threading

from flask import Blueprint, jsonify, request

from api.intake_completion import form_completion_state, load_form_data, persist_completion_state
from api.utils import (
    deployment_info,
    get_db_connection,
    hash_patient_password,
    run_full_clinical_pipeline,
)


submissions_bp = Blueprint("submissions", __name__)


def _normalize_submission_id(submission_id):
    if isinstance(submission_id, str) and submission_id.startswith("INT-"):
        return int(submission_id.split("-")[1])
    return int(submission_id)


def _merge_questionnaire(submission_id, field_name, payload):
    conn = get_db_connection()
    row = conn.execute("SELECT form_data FROM intake_forms WHERE id = ?", (submission_id,)).fetchone()
    if not row:
        conn.close()
        return None

    form_data = load_form_data(row["form_data"])
    form_data[field_name] = payload
    completion_state = form_completion_state(form_data)
    conn.execute(
        "UPDATE intake_forms SET form_data = ? WHERE id = ?",
        (json.dumps(form_data, ensure_ascii=False), submission_id),
    )
    conn.commit()
    persist_completion_state(
        conn,
        submission_id,
        form_data,
        completion_state,
        notify_payload={
            "full_name": form_data.get("fullName") or form_data.get("name") or "",
            "visit_type": form_data.get("visitType") or "",
            "age": form_data.get("age") or "",
        },
    )
    conn.close()
    return completion_state


def _run_pipeline_bg(data_copy, sub_id):
    print(f"[pipeline] submission #{sub_id} started")
    try:
        pipeline_result = run_full_clinical_pipeline(data_copy, submission_id=sub_id)
    except Exception as exc:
        pipeline_result = {
            "status": "error",
            "submission_id": sub_id,
            "error": str(exc),
        }
        print(f"[pipeline] submission #{sub_id} failed: {exc}")
    else:
        print(
            f"[pipeline] submission #{sub_id} finished: "
            f"status={pipeline_result.get('status')} "
            f"stopped_after={pipeline_result.get('stopped_after')}"
        )

    conn_bg = get_db_connection()
    row = conn_bg.execute("SELECT form_data FROM intake_forms WHERE id = ?", (sub_id,)).fetchone()
    current_data = load_form_data(row["form_data"]) if row else dict(data_copy)
    current_data["clinical_pipeline"] = pipeline_result
    conn_bg.execute(
        "UPDATE intake_forms SET form_data = ? WHERE id = ?",
        (json.dumps(current_data, ensure_ascii=False), sub_id),
    )
    conn_bg.commit()
    conn_bg.close()


@submissions_bp.route("/submit", methods=["POST"])
def submit_form():
    """Save a submitted intake form, then run the configured clinical agent workflow."""
    data = request.json or {}
    initial_payload = dict(data)
    patient_password = str(data.get("patientPassword") or "").strip()

    if data.get("patientStatus") == "first_time" and not patient_password:
        return jsonify({"error": "Patient password is required for first-time access."}), 400

    patient_password_hash = hash_patient_password(patient_password) if patient_password else None

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO intake_forms
        (full_name, age, mobile, email, patient_password_hash, form_data)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            data.get("fullName"),
            data.get("age"),
            data.get("mobile"),
            data.get("email"),
            patient_password_hash,
            json.dumps(initial_payload, ensure_ascii=False),
        ),
    )

    submission_id = cur.lastrowid
    initial_payload["clinical_pipeline"] = {
        "status": "running",
        "submission_id": submission_id,
        "stopped_after": None,
        "message": "Clinical workflow is running in the background.",
    }
    cur.execute(
        "UPDATE intake_forms SET form_data = ? WHERE id = ?",
        (json.dumps(initial_payload, ensure_ascii=False), submission_id),
    )
    conn.commit()

    completion_state = form_completion_state(initial_payload)
    persist_completion_state(
        conn,
        submission_id,
        initial_payload,
        completion_state,
        notify_payload={
            "full_name": data.get("fullName") or "Unknown patient",
            "visit_type": data.get("visitType") or "",
            "age": data.get("age") or "",
        },
    )
    conn.close()

    threading.Thread(target=_run_pipeline_bg, args=(dict(data), submission_id), daemon=False).start()

    return jsonify({
        "message": "Form submitted successfully. Clinical workflow is running in the background.",
        "submission_id": submission_id,
        "codeNo": f"INT-{submission_id}",
        "deployment": deployment_info(),
        "completion": completion_state,
    })


@submissions_bp.route("/submit-iief", methods=["POST"])
def submit_iief():
    """Merge the IIEF scores and answers into the patient's submission record."""
    data = request.json or {}
    submission_id = data.get("submission_id")
    iief_data = data.get("iief_data")

    if not submission_id:
        return jsonify({"error": "submission_id is required"}), 400
    if not iief_data:
        return jsonify({"error": "iief_data is required"}), 400

    try:
        submission_id = _normalize_submission_id(submission_id)
    except (ValueError, IndexError):
        return jsonify({"error": "Invalid submission_id format"}), 400

    completion_state = _merge_questionnaire(submission_id, "iief_data", iief_data)
    if completion_state is None:
        return jsonify({"error": f"Submission #{submission_id} not found"}), 404

    return jsonify({
        "message": "IIEF Questionnaire answers submitted successfully.",
        "submission_id": submission_id,
        "codeNo": f"INT-{submission_id}",
        "completion": completion_state,
    })


@submissions_bp.route("/submit-pedt", methods=["POST"])
def submit_pedt():
    """Merge the PEDT scores and answers into the patient's submission record."""
    data = request.json or {}
    submission_id = data.get("submission_id")
    pedt_data = data.get("pedt_data")

    if not submission_id:
        return jsonify({"error": "submission_id is required"}), 400
    if not pedt_data:
        return jsonify({"error": "pedt_data is required"}), 400

    try:
        submission_id = _normalize_submission_id(submission_id)
    except (ValueError, IndexError):
        return jsonify({"error": "Invalid submission_id format"}), 400

    completion_state = _merge_questionnaire(submission_id, "pedt_data", pedt_data)
    if completion_state is None:
        return jsonify({"error": f"Submission #{submission_id} not found"}), 404

    return jsonify({
        "message": "PEDT Questionnaire answers submitted successfully.",
        "submission_id": submission_id,
        "codeNo": f"INT-{submission_id}",
        "completion": completion_state,
    })


@submissions_bp.route("/submit-ehs", methods=["POST"])
def submit_ehs():
    """Merge the Erection Hardness Scale answers into the patient's submission record."""
    data = request.json or {}
    submission_id = data.get("submission_id")
    ehs_data = data.get("ehs_data")

    if not submission_id:
        return jsonify({"error": "submission_id is required"}), 400
    if not ehs_data:
        return jsonify({"error": "ehs_data is required"}), 400

    try:
        submission_id = _normalize_submission_id(submission_id)
    except (ValueError, IndexError):
        return jsonify({"error": "Invalid submission_id format"}), 400

    completion_state = _merge_questionnaire(submission_id, "ehs_data", ehs_data)
    if completion_state is None:
        return jsonify({"error": f"Submission #{submission_id} not found"}), 404

    return jsonify({
        "message": "Erection Hardness Scale answers submitted successfully.",
        "submission_id": submission_id,
        "codeNo": f"INT-{submission_id}",
        "completion": completion_state,
    })


@submissions_bp.route("/submit-low-libido", methods=["POST"])
def submit_low_libido():
    """Merge the Low Libido questionnaire scores into the patient's submission record."""
    data = request.json or {}
    submission_id = data.get("submission_id")
    low_libido_data = data.get("low_libido_data")

    if not submission_id:
        return jsonify({"error": "submission_id is required"}), 400
    if not low_libido_data:
        return jsonify({"error": "low_libido_data is required"}), 400

    try:
        submission_id = _normalize_submission_id(submission_id)
    except (ValueError, IndexError):
        return jsonify({"error": "Invalid submission_id format"}), 400

    completion_state = _merge_questionnaire(submission_id, "low_libido_data", low_libido_data)
    if completion_state is None:
        return jsonify({"error": f"Submission #{submission_id} not found"}), 404

    return jsonify({
        "message": "Low Libido questionnaire answers submitted successfully.",
        "submission_id": submission_id,
        "codeNo": f"INT-{submission_id}",
        "completion": completion_state,
    })
