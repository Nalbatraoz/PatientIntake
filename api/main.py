from flask import Flask, request, jsonify, render_template, send_from_directory, Response
from flask_cors import CORS
import json
import glob
import os
import queue
import re
import threading
import time

from api.utils import (
    ALLOWED_IMAGE_EXTENSIONS,
    ALLOWED_INVESTIGATION_EXTENSIONS,
    BASE_DIR,
    FRONTEND_DIR,
    MAX_UPLOAD_FILES,
    UPLOAD_DIR,
    build_label_flags,
    clamp_int,
    clinical_agent_dependencies,
    clinical_agent_module,
    deployment_info,
    extract_text_with_tesseract,
    format_answer,
    generate_next_patient_code,
    get_db_connection,
    get_patient_by_code,
    init_db,
    build_ai_summary_points,
    first_text,
    lookup_openfda_label,
    parse_possible_drug_names,
    hash_patient_password,
    password_required_response,
    render_ai_report,
    run_full_clinical_pipeline,
    save_uploaded_file,
    submissions_authorized,
)
from core.rag_store import build_clinical_context, index_rag_files, rag_status, search_rag

app = Flask(__name__, template_folder=os.path.join(BASE_DIR, "frontend"))
_notification_lock = threading.Lock()
_notification_listeners = []

_APP_BASE_PATH = os.environ.get("APP_BASE_PATH", "").strip()
if _APP_BASE_PATH and _APP_BASE_PATH != "/":
    _APP_BASE_PATH = "/" + _APP_BASE_PATH.strip("/")
else:
    _APP_BASE_PATH = ""


class _PrefixMiddleware:
    """Allow the app to live behind a reverse-proxy path prefix."""

    def __init__(self, app, prefix):
        self.app = app
        self.prefix = prefix.rstrip("/")

    def __call__(self, environ, start_response):
        prefix = self.prefix
        path_info = environ.get("PATH_INFO", "")
        if prefix and (path_info == prefix or path_info.startswith(prefix + "/")):
            environ["SCRIPT_NAME"] = environ.get("SCRIPT_NAME", "") + prefix
            stripped = path_info[len(prefix):]
            environ["PATH_INFO"] = stripped if stripped else "/"
        return self.app(environ, start_response)


if _APP_BASE_PATH:
    app.config["APPLICATION_ROOT"] = _APP_BASE_PATH
    app.wsgi_app = _PrefixMiddleware(app.wsgi_app, _APP_BASE_PATH)

_COMPLAINT_TO_FORM_KEY = {
    "low_libido": "low_libido_data",
    "premature_ejaculation": "pedt_data",
    "erectile_dysfunction": "ehs_data",
}

_REQUIRED_BASE_FORM_KEYS = ("iief_data",)

def _broadcast_notification(payload):
    data = json.dumps(payload, ensure_ascii=False)
    with _notification_lock:
        dead = []
        for q in _notification_listeners:
            try:
                q.put_nowait(data)
            except queue.Full:
                dead.append(q)
        for q in dead:
            _notification_listeners.remove(q)

def _load_form_data(raw_value):
    """Parse persisted form JSON safely."""
    try:
        return json.loads(raw_value or "{}")
    except json.JSONDecodeError:
        return {}

def _extract_complaints(form_data):
    """Return the patient complaint list as normalized strings."""
    complaints = form_data.get("complaints", [])
    if isinstance(complaints, str):
        complaints = [item.strip() for item in complaints.split(",")]
    if not isinstance(complaints, list):
        return []
    return [str(item).strip() for item in complaints if str(item).strip()]

def _required_form_keys(form_data):
    """Return the questionnaire keys needed before the intake is complete."""
    required = set(_REQUIRED_BASE_FORM_KEYS)
    for complaint in _extract_complaints(form_data):
        form_key = _COMPLAINT_TO_FORM_KEY.get(complaint)
        if form_key:
            required.add(form_key)
    return required

def _form_completion_state(form_data):
    """Compute which patient questionnaire sections are complete."""
    required = sorted(_required_form_keys(form_data))
    completed = sorted(
        key for key in required
        if form_data.get(key)
    )
    is_complete = len(completed) == len(required)
    completion = form_data.get("completion") if isinstance(form_data.get("completion"), dict) else {}
    return {
        "required_forms": required,
        "completed_forms": completed,
        "is_complete": is_complete,
        "notified": bool(completion.get("notified")),
        "completed_at": completion.get("completed_at"),
    }

def _persist_completion_state(conn, submission_id, form_data, completion_state, notify_payload=None):
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
        payload = {
            "type": "new_submission",
            "submission_id": submission_id,
            "full_name": notify_payload.get("full_name") or "",
            "visit_type": notify_payload.get("visit_type") or "",
            "age": str(notify_payload.get("age") or ""),
            "codeNo": f"INT-{submission_id}",
            "timestamp": time.strftime("%H:%M"),
        }
        _broadcast_notification(payload)

    return updated_completion


def _public_upload_url(relative_path):
    """Build a public uploads URL that respects the reverse-proxy prefix."""
    relative_path = str(relative_path or "").replace("\\", "/").lstrip("/")
    if _APP_BASE_PATH:
        return f"{_APP_BASE_PATH}/uploads/{relative_path}"
    return f"/uploads/{relative_path}"


def _resolve_report_pdf_url(report_pdf, code_no):
    """Return a report PDF URL only when a real file exists on disk."""
    report_pdf = report_pdf or {}
    candidate_paths = []

    relative_path = str(report_pdf.get("relative_path") or "").strip().replace("\\", "/").lstrip("/")
    if relative_path:
        candidate_paths.append(relative_path)

    url = str(report_pdf.get("url") or "").strip()
    if url.startswith("/uploads/"):
        candidate_paths.append(url.removeprefix("/uploads/"))
    if _APP_BASE_PATH and url.startswith(f"{_APP_BASE_PATH}/uploads/"):
        candidate_paths.append(url.removeprefix(f"{_APP_BASE_PATH}/uploads/"))

    for relative in candidate_paths:
        full_path = os.path.join(UPLOAD_DIR, relative)
        if os.path.exists(full_path):
            return _public_upload_url(relative)

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
            return _public_upload_url(relative)

    return None
CORS(app)
app.config["MAX_CONTENT_LENGTH"] = 30 * 1024 * 1024

@app.route("/")
def website():
    """Serve the main intake form page."""
    return send_from_directory(FRONTEND_DIR, "index.html")

@app.route("/style.css")
def css():
    """Serve the frontend stylesheet."""
    return send_from_directory(FRONTEND_DIR, "style.css")

@app.route("/script.js")
def js():
    """Serve the frontend JavaScript file."""
    return send_from_directory(FRONTEND_DIR, "script.js")

@app.route("/notifications.js")
def notifications_js():
    return send_from_directory(FRONTEND_DIR, "notifications.js")

@app.route("/notifications.css")  
def notifications_css():
    return send_from_directory(FRONTEND_DIR, "notifications.css")

@app.route("/submissions.css")
def submissions_css():
    """Serve the submissions page stylesheet."""
    return send_from_directory(FRONTEND_DIR, "submissions.css")

@app.route("/submissions.js")
def submissions_js():
    """Serve the submissions page JavaScript file."""
    return send_from_directory(FRONTEND_DIR, "submissions.js")

@app.route("/pedt")
def pedt_page():
    return send_from_directory(FRONTEND_DIR, "pedt.html")

@app.route("/pedt.css")
def pedt_css():
    return send_from_directory(FRONTEND_DIR, "pedt.css")

@app.route("/pedt.js")
def pedt_js():
    return send_from_directory(FRONTEND_DIR, "pedt.js")

@app.route("/ehs")
def ehs_page():
    """Serve the Erection Hardness Scale page."""
    return send_from_directory(FRONTEND_DIR, "ehs.html")

@app.route("/ehs.css")
def ehs_css():
    """Serve the Erection Hardness Scale stylesheet."""
    return send_from_directory(FRONTEND_DIR, "ehs.css")

@app.route("/ehs.js")
def ehs_js():
    """Serve the Erection Hardness Scale JavaScript logic."""
    return send_from_directory(FRONTEND_DIR, "ehs.js")

@app.route("/low-libido")
def low_libido_page():
    """Serve the Low Libido Questionnaire page."""
    return send_from_directory(FRONTEND_DIR, "low-libido.html")

@app.route("/low-libido.css")
def low_libido_css():
    """Serve the Low Libido Questionnaire stylesheet."""
    return send_from_directory(FRONTEND_DIR, "low-libido.css")

@app.route("/low-libido.js")
def low_libido_js():
    """Serve the Low Libido Questionnaire JavaScript logic."""
    return send_from_directory(FRONTEND_DIR, "low-libido.js")

@app.route("/iief")
def iief_page():
    """Serve the IIEF Questionnaire page."""
    return send_from_directory(FRONTEND_DIR, "iief.html")

@app.route("/iief.css")
def iief_css():
    """Serve the IIEF Questionnaire stylesheet."""
    return send_from_directory(FRONTEND_DIR, "iief.css")

@app.route("/iief.js")
def iief_js():
    """Serve the IIEF Questionnaire JavaScript logic."""
    return send_from_directory(FRONTEND_DIR, "iief.js")

@app.route("/clinical-agent-test.css")
def clinical_agent_test_css():
    """Serve the clinical agent test page stylesheet."""
    return send_from_directory(FRONTEND_DIR, "clinical-agent-test.css")

@app.route("/clinical-agent-test.js")
def clinical_agent_test_js():
    """Serve the clinical agent test page JavaScript file."""
    return send_from_directory(FRONTEND_DIR, "clinical-agent-test.js")

@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    """Serve a protected uploaded file after validating the requested path is safe."""
    normalized = os.path.normpath(filename)
    if normalized.startswith("..") or os.path.isabs(normalized):
        return Response("Invalid upload path.", 400)

    is_report_pdf = normalized.replace("\\", "/").startswith("reports/")
    if not is_report_pdf and not submissions_authorized():
        return password_required_response()

    directory = os.path.join(UPLOAD_DIR, os.path.dirname(normalized))
    basename = os.path.basename(normalized)
    full_path = os.path.join(directory, basename)

    if not os.path.exists(full_path) and is_report_pdf:
        report_match = re.search(r"INT-[A-Za-z0-9_-]+", basename, re.IGNORECASE)
        if report_match:
            code_token = report_match.group(0)
            patterns = [
                f"*{code_token}*.pdf",
                f"*({code_token}).pdf",
                f"*-{code_token}.pdf",
            ]
            for pattern in patterns:
                matches = sorted(
                    glob.glob(os.path.join(UPLOAD_DIR, "reports", "**", pattern), recursive=True)
                )
                if matches:
                    directory = os.path.dirname(matches[0])
                    basename = os.path.basename(matches[0])
                    full_path = matches[0]
                    break

    if not os.path.exists(full_path):
        return Response("Report PDF not found.", 404)

    response = send_from_directory(directory, basename)
    if is_report_pdf:
        response.headers["Cache-Control"] = "no-store, max-age=0"
    return response

@app.route("/patient-code/next")
def generate_patient_code():
    """Generate and return the next available patient code."""
    code_no = generate_next_patient_code()
    return jsonify({
        "codeNo": code_no,
        "message": f"Generated new patient code: {code_no}",
    })

@app.route("/patient-code/<code>")
def lookup_patient_code(code):
    """Look up an existing patient by their code."""
    password = request.args.get("password") or ""
    patient = get_patient_by_code(code, password=password)
    
    if not patient:
        return jsonify({
            "found": False,
            "error": "Patient record not found or password is incorrect.",
        }), 401
    
    return jsonify({
        "found": True,
        "codeNo": patient["codeNo"],
        "full_name": patient["full_name"],
        "name": patient["full_name"],
        "age": patient["age"],
        "mobile": patient["mobile"],
        "phone": patient["mobile"],
        "email": patient["email"],
        "form_data": patient["form_data"],
    })


@app.route("/patient-code/lookup", methods=["POST"])
def lookup_patient_code_with_password():
    """Look up a patient record using their code and patient password."""
    data = request.get_json(silent=True) or {}
    code = str(data.get("codeNo") or data.get("code") or "").strip()
    password = str(data.get("password") or "").strip()

    if not code:
        return jsonify({"found": False, "error": "Patient code is required."}), 400

    patient = get_patient_by_code(code, password=password)
    if not patient:
        return jsonify({
            "found": False,
            "error": "Patient record not found or password is incorrect.",
        }), 401

    return jsonify({
        "found": True,
        "codeNo": patient["codeNo"],
        "full_name": patient["full_name"],
        "name": patient["full_name"],
        "age": patient["age"],
        "mobile": patient["mobile"],
        "phone": patient["mobile"],
        "email": patient["email"],
        "form_data": patient["form_data"],
    })

@app.route("/scan-drugs", methods=["POST"])
def scan_drugs():
    """Handle medication image uploads, OCR them, and run openFDA checks."""
    saved_files = []
    errors = []

    upload_groups = [
        ("drugImages", "drug-images", ALLOWED_IMAGE_EXTENSIONS),
        ("investigationFiles", "investigations", ALLOWED_INVESTIGATION_EXTENSIONS),
    ]

    for field_name, category, allowed_extensions in upload_groups:
        for file_obj in request.files.getlist(field_name)[:MAX_UPLOAD_FILES]:
            try:
                saved = save_uploaded_file(file_obj, category, allowed_extensions)
                if saved:
                    saved_files.append(saved)
            except ValueError as exc:
                errors.append(str(exc))

    current_medications = request.form.get("currentMedications", "")
    medical_history = request.form.get("medicalHistory", "")

    has_drug_images = any(file_info.get("category") == "drug-images" for file_info in saved_files)
    ocr_note = None
    ocr_scan = None

    if has_drug_images:
        ocr_scan, ocr_note = extract_text_with_tesseract(saved_files)

    extracted_text = ""
    extracted_names = []
    scan_source = "manual_text"

    if ocr_scan:
        scan_source = "local_ocr"
        extracted_text = first_text(ocr_scan.get("observed_text"), 2000)
        extracted_names = [
            str(name).strip()
            for name in ocr_scan.get("drug_names", [])
            if str(name).strip()
        ]

    drug_candidates = []
    for name in extracted_names + parse_possible_drug_names(current_medications, extracted_text):
        key = name.lower()
        if key not in {candidate.lower() for candidate in drug_candidates}:
            drug_candidates.append(name)
        if len(drug_candidates) >= MAX_LOOKUP_NAMES:
            break

    openfda_results = [lookup_openfda_label(name) for name in drug_candidates]
    label_flags = build_label_flags(openfda_results, current_medications, medical_history)

    notes = [
        "This scan supports intake review only and is not a diagnosis, prescription, or medication-safety decision. / هذا الفحص لمراجعة بيانات الاستبيان فقط وليس تشخيصًا أو وصفة أو قرارًا علاجيًا.",
        "Confirm all detected medication names, strengths, and warnings with a licensed clinician. / يجب تأكيد أسماء الأدوية والجرعات والتحذيرات مع طبيب مختص.",
    ]
    for note in (ocr_note,):
        if note:
            notes.append(note)
    notes.extend(errors)

    return jsonify({
        "message": "Upload received and medication lookup completed. / تم استلام الملفات وإكمال البحث عن الأدوية.",
        "files": saved_files,
        "scan_source": scan_source,
        "extracted_text": extracted_text,
        "drug_candidates": drug_candidates,
        "openfda": openfda_results,
        "label_flags": label_flags,
        "notes": notes,
        "deployment": deployment_info(),
    })
 

@app.route("/submissions")
def submissions():
    """Render a password-protected HTML page listing all submitted intake forms."""
    if not submissions_authorized():
        return password_required_response()

    conn = get_db_connection()
    rows = conn.execute("""
        SELECT id, full_name, age, mobile, email, form_data
        FROM intake_forms
        ORDER BY id DESC
    """).fetchall()
    conn.close()

    submissions = []
    for row in rows:
        form_data = _load_form_data(row["form_data"])

        pipeline = form_data.pop("clinical_pipeline", None)
        iief_data = form_data.pop("iief_data", None)
        pedt_data = form_data.pop("pedt_data", None)
        ehs_data = form_data.pop("ehs_data", None)
        low_libido_data = form_data.pop("low_libido_data", None)
        report_pdf = (pipeline or {}).get("report_pdf") or {}
        uploaded_files = form_data.pop("uploadedFiles", None)
        submission_id = row["id"]
        code_no = f"INT-{submission_id}"
        report_pdf_url = _resolve_report_pdf_url(report_pdf, code_no)
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
            "upload_panel_id": f"upload-panel-{submission_id}",
            "iief_panel_id": f"iief-panel-{submission_id}",
            "pedt_panel_id": f"pedt-panel-{submission_id}",
            "ehs_panel_id": f"ehs-panel-{submission_id}",
            "low_libido_panel_id": f"low-libido-panel-{submission_id}",
            "report_pdf_url": report_pdf_url,
            "report_pdf_error": report_pdf.get("error"),
            "uploaded_files": uploaded_files,
            "ai_summary_points": build_ai_summary_points(pipeline),
            "iief_data": iief_data,
            "pedt_data": pedt_data,
            "ehs_data": ehs_data,
            "low_libido_data": low_libido_data,
            "answers": [
                {"key": str(key), "value": format_answer(value)}
                for key, value in form_data.items()
                if key not in ("clinical_pipeline", "completion", "iief_data", "pedt_data", "ehs_data", "low_libido_data", "uploadedFiles")
            ],
            "ai_html": render_ai_report(pipeline),
        })

    return render_template("submissions.html", submissions=submissions)

@app.route("/submit", methods=["POST"])
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
    cur.execute("""
        INSERT INTO intake_forms 
        (full_name, age, mobile, email, patient_password_hash, form_data)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        data.get("fullName"),
        data.get("age"),
        data.get("mobile"),
        data.get("email"),
        patient_password_hash,
        json.dumps(initial_payload, ensure_ascii=False)
    ))

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

    completion_state = _form_completion_state(initial_payload)
    _persist_completion_state(
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

    # Spawn background thread to run clinical pipeline
    def run_pipeline_bg(data_copy, sub_id):
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
        if row:
            current_data = _load_form_data(row["form_data"])
        else:
            current_data = dict(data_copy)

        current_data["clinical_pipeline"] = pipeline_result
        conn_bg.execute(
            "UPDATE intake_forms SET form_data = ? WHERE id = ?",
            (json.dumps(current_data, ensure_ascii=False), sub_id),
        )
        conn_bg.commit()
        conn_bg.close()

    threading.Thread(target=run_pipeline_bg, args=(dict(data), submission_id), daemon=False).start()

    return jsonify({
        "message": "Form submitted successfully. Clinical workflow is running in the background.",
        "submission_id": submission_id,
        "codeNo": f"INT-{submission_id}",
        "deployment": deployment_info(),
        "completion": completion_state,
    })


@app.route("/submit-iief", methods=["POST"])
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
        # Extract integer ID from patient code if passed as a string (e.g. INT-123 -> 123)
        if isinstance(submission_id, str) and submission_id.startswith("INT-"):
            submission_id = int(submission_id.split("-")[1])
        else:
            submission_id = int(submission_id)
    except (ValueError, IndexError):
        return jsonify({"error": "Invalid submission_id format"}), 400

    conn = get_db_connection()
    row = conn.execute("SELECT form_data FROM intake_forms WHERE id = ?", (submission_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": f"Submission #{submission_id} not found"}), 404

    form_data = _load_form_data(row["form_data"])

    # Merge IIEF data
    form_data["iief_data"] = iief_data
    completion_state = _form_completion_state(form_data)

    conn.execute(
        "UPDATE intake_forms SET form_data = ? WHERE id = ?",
        (json.dumps(form_data, ensure_ascii=False), submission_id),
    )
    conn.commit()
    _persist_completion_state(
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

    return jsonify({
        "message": "IIEF Questionnaire answers submitted successfully.",
        "submission_id": submission_id,
        "codeNo": f"INT-{submission_id}",
        "completion": completion_state,
    })


@app.route("/submit-pedt", methods=["POST"])
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
        # Extract integer ID from patient code if passed as a string (e.g. INT-123 -> 123)
        if isinstance(submission_id, str) and submission_id.startswith("INT-"):
            submission_id = int(submission_id.split("-")[1])
        else:
            submission_id = int(submission_id)
    except (ValueError, IndexError):
        return jsonify({"error": "Invalid submission_id format"}), 400

    conn = get_db_connection()
    row = conn.execute("SELECT form_data FROM intake_forms WHERE id = ?", (submission_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": f"Submission #{submission_id} not found"}), 404

    form_data = _load_form_data(row["form_data"])

    # Merge PEDT data
    form_data["pedt_data"] = pedt_data
    completion_state = _form_completion_state(form_data)

    conn.execute(
        "UPDATE intake_forms SET form_data = ? WHERE id = ?",
        (json.dumps(form_data, ensure_ascii=False), submission_id),
    )
    conn.commit()
    _persist_completion_state(
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

    return jsonify({
        "message": "PEDT Questionnaire answers submitted successfully.",
        "submission_id": submission_id,
        "codeNo": f"INT-{submission_id}",
        "completion": completion_state,
    })


@app.route("/submit-ehs", methods=["POST"])
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
        if isinstance(submission_id, str) and submission_id.startswith("INT-"):
            submission_id = int(submission_id.split("-")[1])
        else:
            submission_id = int(submission_id)
    except (ValueError, IndexError):
        return jsonify({"error": "Invalid submission_id format"}), 400

    conn = get_db_connection()
    row = conn.execute("SELECT form_data FROM intake_forms WHERE id = ?", (submission_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": f"Submission #{submission_id} not found"}), 404

    form_data = _load_form_data(row["form_data"])

    form_data["ehs_data"] = ehs_data
    completion_state = _form_completion_state(form_data)

    conn.execute(
        "UPDATE intake_forms SET form_data = ? WHERE id = ?",
        (json.dumps(form_data, ensure_ascii=False), submission_id),
    )
    conn.commit()
    _persist_completion_state(
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

    return jsonify({
        "message": "Erection Hardness Scale answers submitted successfully.",
        "submission_id": submission_id,
        "codeNo": f"INT-{submission_id}",
        "completion": completion_state,
    })


@app.route("/submit-low-libido", methods=["POST"])
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
        if isinstance(submission_id, str) and submission_id.startswith("INT-"):
            submission_id = int(submission_id.split("-")[1])
        else:
            submission_id = int(submission_id)
    except (ValueError, IndexError):
        return jsonify({"error": "Invalid submission_id format"}), 400

    conn = get_db_connection()
    row = conn.execute("SELECT form_data FROM intake_forms WHERE id = ?", (submission_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": f"Submission #{submission_id} not found"}), 404

    form_data = _load_form_data(row["form_data"])

    form_data["low_libido_data"] = low_libido_data
    completion_state = _form_completion_state(form_data)

    conn.execute(
        "UPDATE intake_forms SET form_data = ? WHERE id = ?",
        (json.dumps(form_data, ensure_ascii=False), submission_id),
    )
    conn.commit()
    _persist_completion_state(
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

    return jsonify({
        "message": "Low Libido questionnaire answers submitted successfully.",
        "submission_id": submission_id,
        "codeNo": f"INT-{submission_id}",
        "completion": completion_state,
    })


@app.route("/rag/status")
def rag_status_route():
    """Return the current indexing/search status for the local RAG document store."""
    if not submissions_authorized():
        return password_required_response()

    status = rag_status()
    status["deployment"] = deployment_info()
    return jsonify(status)

@app.route("/rag/index", methods=["POST"])
def rag_index_route():
    """Index uploaded/reference files into the local RAG store."""
    if not submissions_authorized():
        return password_required_response()

    options = request.get_json(silent=True) or {}
    try:
        result = index_rag_files(
            force=bool(options.get("force")),
            limit=options.get("limit"),
        )
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 400

    result["deployment"] = deployment_info()
    return jsonify(result)

@app.route("/rag/search", methods=["POST"])
def rag_search_route():
    """Search the local RAG store and return the most relevant source passages."""
    if not submissions_authorized():
        return password_required_response()

    data = request.get_json(silent=True) or {}
    query = str(data.get("query") or "").strip()
    if not query:
        return jsonify({"error": "query is required"}), 400

    top_k = clamp_int(data.get("top_k"), 6, 1, 12)
    try:
        result = search_rag(query, top_k=top_k)
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 400

    result["deployment"] = deployment_info()
    return jsonify(result)

@app.route("/rag/context", methods=["POST"])
def rag_context_route():
    """Build a combined clinical context block from the top RAG search results."""
    if not submissions_authorized():
        return password_required_response()

    data = request.get_json(silent=True) or {}
    query = str(data.get("query") or "").strip()
    if not query:
        return jsonify({"error": "query is required"}), 400

    top_k = clamp_int(data.get("top_k"), 6, 1, 12)
    try:
        result = build_clinical_context(query, top_k=top_k)
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 400

    result["deployment"] = deployment_info()
    return jsonify(result)

@app.route("/events")
def sse_events():
    """
    Server-Sent Events stream for real-time doctor notifications.
    The doctor's page connects once; we push a 'new_submission' event
    each time a patient completes and submits the intake form.
    """
    if not submissions_authorized():
        return password_required_response()
 
    def stream():
        q: queue.Queue = queue.Queue(maxsize=20)
        with _notification_lock:
            _notification_listeners.append(q)
        try:
            # Initial ping confirms the connection is live.
            yield "event: connected\ndata: {}\n\n"
            while True:
                try:
                    data = q.get(timeout=25)
                    yield f"event: new_submission\ndata: {data}\n\n"
                except queue.Empty:
                    # Keepalive comment — prevents proxies from killing idle connections.
                    yield ": keepalive\n\n"
        except GeneratorExit:
            pass
        finally:
            with _notification_lock:
                try:
                    _notification_listeners.remove(q)
                except ValueError:
                    pass
 
    return Response(
        stream(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
 
 

@app.route("/clinical-agent-test")
def clinical_agent_test_page():
    """Serve a protected browser test page for calling the clinical agent endpoint."""
    if not submissions_authorized():
        return password_required_response()

    return render_template("clinical-agent-test.html")

@app.route("/clinical-agent", methods=["POST"])
def clinical_agent_route():
    """Build and return the clinical agent packet for the supplied patient/query data."""
    if not submissions_authorized():
        return password_required_response()

    data = request.get_json(silent=True) or {}
    try:
        result = clinical_agent_module.build_clinical_agent_response(
            data,
            clinical_agent_dependencies(),
        )
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 400

    result["deployment"] = deployment_info()
    return jsonify(result)

if __name__ == "__main__":
    init_db()
    debug_mode = os.environ.get("FLASK_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}
    host = os.environ.get("FLASK_HOST", "0.0.0.0").strip() or "0.0.0.0"
    port = int(os.environ.get("FLASK_PORT", "5001"))
    app.run(host=host, port=port, debug=debug_mode, use_reloader=False)
