import hmac
import json
import os
import re
import sqlite3
import uuid
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode

from flask import Response, render_template, request
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash, generate_password_hash

from core.agent_utils import compact_text as first_text
from core.agent_utils import load_secret as read_secret
from core.agent_utils import request_json
from core.crew_orchestrator import run_full_clinical_pipeline as orchestrate_full_clinical_pipeline
from nodes.RAG_agent import retrieve_clinical_context
import nodes.agents as clinical_agent_module
from nodes.agents import (
    build_arabic_pdf_report,
    run_evidence_reviewer_agent,
    run_lifestyle_agent,
    run_report_agent,
    run_research_agent,
    save_report_pdf,
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
DB_PATH = os.environ.get("DB_PATH") or os.path.join(BASE_DIR, "intake.db")
UPLOAD_DIR = os.environ.get("UPLOAD_DIR") or os.path.join(BASE_DIR, "uploads")
STORAGE_BACKEND = os.environ.get("STORAGE_BACKEND") or "local_filesystem"
STORAGE_IS_EPHEMERAL = False
APP_BASE_PATH = os.environ.get("APP_BASE_PATH", "").strip()
if APP_BASE_PATH and APP_BASE_PATH != "/":
    APP_BASE_PATH = "/" + APP_BASE_PATH.strip("/")
else:
    APP_BASE_PATH = ""

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

if load_dotenv:
    load_dotenv(os.path.join(BASE_DIR, ".env"), override=False)


def deployment_info():
    """Return storage/runtime metadata useful for deployed clients and admin routes."""
    return {
        "platform": "local",
        "storage_backend": STORAGE_BACKEND,
        "storage_ephemeral": STORAGE_IS_EPHEMERAL,
        "database_path": DB_PATH,
        "upload_dir": UPLOAD_DIR,
    }

# Purpose: map the local APIkey file names accepted by the app.
SECRET_ALIASES = {
    "GEMINI_API_KEY": {"GEMINI_API_KEY", "GOOGLE_API_KEY", "GEMINI", "GOOGLE"},
    "OPENFDA_API_KEY": {"OPENFDA_API_KEY", "OPEN_FDA_API_KEY", "OPENFDA", "FDA_API_KEY"},
}


def load_secret(name):
    """Read a named secret from env vars or the local APIkey file."""
    return read_secret(
        name,
        base_dir=BASE_DIR,
        aliases=SECRET_ALIASES.get(name, {name}),
        bare_value=lambda line: name == "OPENFDA_API_KEY" or (
            name == "GEMINI_API_KEY" and line.startswith("AIza")
        ),
    )


def public_upload_url(relative_path):
    """Build a public uploads URL that respects any reverse-proxy path prefix."""
    relative_path = str(relative_path or "").replace("\\", "/").lstrip("/")
    prefix = APP_BASE_PATH.rstrip("/")
    if prefix:
        return f"{prefix}/uploads/{relative_path}"
    return f"/uploads/{relative_path}"

SUBMISSIONS_PASSWORD = os.environ.get("SUBMISSIONS_PASSWORD", "Doctor")
OPENFDA_API_KEY = load_secret("OPENFDA_API_KEY")
DRUGBANK_API_KEY = load_secret("DRUGBANK_API_KEY")
DRUGBANK_REGION = os.environ.get("DRUGBANK_REGION", "us")
GEMINI_API_KEY = load_secret("GEMINI_API_KEY")
GEMINI_CLINICAL_MODEL = os.environ.get("GEMINI_CLINICAL_MODEL", "gemini-2.5-flash")
GEMINI_RESEARCH_MODEL = os.environ.get("GEMINI_RESEARCH_MODEL", "gemini-2.5-flash")
GEMINI_EVIDENCE_REVIEWER_MODEL = os.environ.get("GEMINI_EVIDENCE_REVIEWER_MODEL", "gemini-2.5-flash")
GEMINI_REPORT_MODEL = os.environ.get("GEMINI_REPORT_MODEL", "gemini-2.5-flash")
TESSERACT_CMD = os.environ.get("TESSERACT_CMD", "").strip()
TESSERACT_LANG = os.environ.get("TESSERACT_LANG", "eng").strip() or "eng"
TESSERACT_CONFIG = os.environ.get("TESSERACT_CONFIG", "").strip()

ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif", "bmp", "tif", "tiff"}
ALLOWED_INVESTIGATION_EXTENSIONS = ALLOWED_IMAGE_EXTENSIONS | {"pdf"}
MAX_UPLOAD_FILES = 12
MAX_LOOKUP_NAMES = 8

STOP_MEDICATION_WORDS = {
    "after", "as", "before", "bid", "box", "cap", "capsule", "capsules", "current",
    "currently", "daily", "bmp", "dose", "drug", "each", "every", "for", "former",
    "gif", "image", "img", "in", "injection",
    "jpeg", "jpg",
    "last", "medicine", "medication", "medications", "month", "months", "morning",
    "needed", "night", "nightly", "once", "oral", "pack", "patient", "pdf",
    "photo", "pill", "png", "previous", "previously", "prn", "qid", "scan",
    "started", "stopped", "sublingual", "tablet", "tablets", "take", "takes",
    "taking", "the", "tid", "tif", "tiff", "tried", "twice", "use", "used", "uses",
    "using", "webp", "with", "year", "years",
}

DOSE_PATTERN = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:mg|mcg|g|kg|ml|iu|units?|%|mmol|meq)\b",
    re.IGNORECASE,
)

def get_db_connection():
    """Open the SQLite intake database and return rows that can be accessed by column name."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS intake_forms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT,
            age INTEGER,
            mobile TEXT,
            email TEXT,
            form_data TEXT
        )
    """)
    conn.commit()
    ensure_intake_form_schema(conn)
    return conn


def ensure_intake_form_schema(conn):
    """Add optional intake form columns that newer app versions rely on."""
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(intake_forms)")
    existing_columns = {row[1] for row in cur.fetchall()}

    if "patient_password_hash" not in existing_columns:
        cur.execute("ALTER TABLE intake_forms ADD COLUMN patient_password_hash TEXT")
        conn.commit()

def generate_next_patient_code():
    """Generate the next available patient code (e.g., INT-1, INT-2, etc.)."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT MAX(id) FROM intake_forms")
    result = cur.fetchone()
    conn.close()
    
    max_id = result[0] if result and result[0] else 0
    next_id = max_id + 1
    return f"INT-{next_id}"

def get_patient_by_code(code, password=None):
    """Look up a patient record by code and verify the patient password when present."""
    if not code or not isinstance(code, str):
        return None
    
    try:
        # Extract the number from the code (e.g., "INT-1" -> 1)
        parts = code.strip().upper().split("-")
        if len(parts) != 2 or parts[0] != "INT":
            return None
        
        patient_id = int(parts[1])
    except (ValueError, IndexError):
        return None
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, full_name, age, mobile, email, form_data, patient_password_hash FROM intake_forms WHERE id = ?",
        (patient_id,),
    )
    row = cur.fetchone()
    conn.close()
    
    if not row:
        return None
    
    try:
        form_data = json.loads(row["form_data"] or "{}")
    except json.JSONDecodeError:
        form_data = {}

    stored_hash = row["patient_password_hash"] or ""
    password = password or ""
    if stored_hash:
        if not password or not check_password_hash(stored_hash, password):
            return None

    return {
        "id": row["id"],
        "codeNo": f"INT-{row['id']}",
        "full_name": row["full_name"],
        "age": row["age"],
        "mobile": row["mobile"],
        "email": row["email"],
        "form_data": form_data,
        "password_required": bool(stored_hash),
    }


def hash_patient_password(password):
    """Hash a patient-chosen password for storage."""
    password = str(password or "").strip()
    if not password:
        raise ValueError("Patient password is required.")
    return generate_password_hash(password)

def safe_json_loads(value, fallback=None):
    """Parse JSON strings safely while returning a fallback for empty or invalid values."""
    if fallback is None:
        fallback = {}
    if isinstance(value, (dict, list)):
        return value
    if not isinstance(value, str) or not value.strip():
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback

def format_answer(value):
    """Convert a saved form answer into structured data for the submissions page."""
    value = safe_json_loads(value, value)

    if isinstance(value, list) and value and all(isinstance(item, dict) and item.get("url") for item in value):
        links = []
        for item in value:
            url = str(item.get("url", ""))
            links.append({
                "url": url if url.startswith("/uploads/") else "",
                "name": str(item.get("original_name") or item.get("stored_name") or "Uploaded file"),
            })
        return {"type": "links", "links": links}

    if isinstance(value, list):
        return {"type": "text", "text": ", ".join(str(item) for item in value)}

    if isinstance(value, dict):
        return {"type": "text", "text": json.dumps(value, ensure_ascii=False, indent=2)}

    return {"type": "text", "text": "" if value is None else str(value)}

def submissions_authorized():
    """Check whether the current request supplied the correct Basic Auth password."""
    auth = request.authorization
    return bool(auth and hmac.compare_digest(auth.password or "", SUBMISSIONS_PASSWORD))

def password_required_response():
    """Return the 401 response that asks the browser to show a password prompt."""
    return Response(
        "Password required to view submitted forms.",
        401,
        {"WWW-Authenticate": 'Basic realm="Submitted Forms"'}
    )

def clamp_int(value, default, minimum, maximum):
    """Convert a value to an integer and keep it inside the supplied inclusive range."""
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, number))

def allowed_extension(filename, allowed_extensions):
    """Return True when the filename has one of the allowed extensions."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in allowed_extensions

def save_uploaded_file(file_obj, category, allowed_extensions):
    """Validate and save one uploaded file, then return metadata used by later routes."""
    if not file_obj or not file_obj.filename:
        return None

    if not allowed_extension(file_obj.filename, allowed_extensions):
        raise ValueError(f"{file_obj.filename} has an unsupported file type.")

    original_name = file_obj.filename
    filename = secure_filename(original_name) or "upload"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    date_folder = datetime.utcnow().strftime("%Y%m%d")
    stored_name = f"{uuid.uuid4().hex}.{ext}"
    relative_path = os.path.join(category, date_folder, stored_name)
    destination_dir = os.path.join(UPLOAD_DIR, category, date_folder)
    os.makedirs(destination_dir, exist_ok=True)
    destination_path = os.path.join(destination_dir, stored_name)
    file_obj.save(destination_path)

    return {
        "category": category,
        "original_name": original_name,
        "stored_name": stored_name,
        "relative_path": relative_path.replace(os.sep, "/"),
        "url": public_upload_url(relative_path),
        "size": os.path.getsize(destination_path),
        "content_type": file_obj.mimetype or "",
        "extension": ext,
        "saved_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "storage_backend": STORAGE_BACKEND,
        "ephemeral": STORAGE_IS_EPHEMERAL,
    }

def list_value(value):
    """Normalize a scalar or list from an API response into a list of non-empty strings."""
    if isinstance(value, list):
        return [str(item) for item in value if item]
    if value:
        return [str(value)]
    return []

def openfda_quote(value):
    """Escape a search term so openFDA treats it as a quoted exact-value query."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'

def summarize_openfda_label(record):
    """Extract the useful medication label fields from one raw openFDA label record."""
    openfda = record.get("openfda") or {}
    return {
        "brand_names": list_value(openfda.get("brand_name")),
        "generic_names": list_value(openfda.get("generic_name")),
        "substance_names": list_value(openfda.get("substance_name")),
        "manufacturer_names": list_value(openfda.get("manufacturer_name")),
        "routes": list_value(openfda.get("route")),
        "dosage_forms": list_value(openfda.get("dosage_form")),
        "product_ndcs": list_value(openfda.get("product_ndc")),
        "rxnorm_ids": list_value(openfda.get("rxcui")),
        "purpose": first_text(record.get("purpose"), 600),
        "indications": first_text(record.get("indications_and_usage"), 800),
        "warnings": first_text(record.get("warnings"), 900),
        "contraindications": first_text(record.get("contraindications"), 700),
        "drug_interactions": first_text(record.get("drug_interactions"), 900),
        "adverse_reactions": first_text(record.get("adverse_reactions"), 700),
    }

def lookup_openfda_label(drug_name):
    """Look up one drug name in openFDA and return a compact label summary or error."""
    params = {"limit": 1}
    if OPENFDA_API_KEY:
        params["api_key"] = OPENFDA_API_KEY

    searches = [
        f"openfda.brand_name:{openfda_quote(drug_name)}",
        f"openfda.generic_name:{openfda_quote(drug_name)}",
        f"openfda.substance_name:{openfda_quote(drug_name)}",
        openfda_quote(drug_name),
    ]

    for search in searches:
        params["search"] = search
        url = "https://api.fda.gov/drug/label.json?" + urlencode(params)
        try:
            payload = request_json(url)
            results = payload.get("results") or []
            if results:
                return {
                    "query": drug_name,
                    "found": True,
                    "source": "openFDA drug label",
                    "search": search,
                    "label": summarize_openfda_label(results[0]),
                }
        except HTTPError as exc:
            if exc.code == 404:
                continue
            return {"query": drug_name, "found": False, "error": f"openFDA returned HTTP {exc.code}"}
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            return {"query": drug_name, "found": False, "error": f"openFDA lookup failed: {exc}"}

    return {"query": drug_name, "found": False, "message": "No matching openFDA label found."}

def parse_possible_drug_names(*texts):
    """Find likely medication names in free text by removing doses and common filler words."""
    candidates = []
    seen = set()

    for text in texts:
        if not text:
            continue
        parts = re.split(r"[\n,;|/]+", str(text))
        for part in parts:
            cleaned = DOSE_PATTERN.sub(" ", part)
            cleaned = re.sub(r"\([^)]*\)", " ", cleaned)
            cleaned = re.sub(r"[^A-Za-z0-9+.\- ]+", " ", cleaned)
            words = [
                word for word in cleaned.split()
                if word.lower() not in STOP_MEDICATION_WORDS and not word.isdigit()
            ]
            if not words:
                continue
            candidate = " ".join(words[:4]).strip(" .-")
            key = candidate.lower()
            if len(candidate) < 3 or key in seen:
                continue
            seen.add(key)
            candidates.append(candidate)
            if len(candidates) >= MAX_LOOKUP_NAMES:
                return candidates

    return candidates

def extract_text_with_tesseract(saved_files):
    """Use local Tesseract OCR to read text from uploaded drug images."""
    try:
        from PIL import Image
        import pytesseract
    except ImportError:
        return None, "Local OCR is not installed. Install Pillow and pytesseract to enable OCR."

    if TESSERACT_CMD:
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

    try:
        pytesseract.get_tesseract_version()
    except Exception as exc:
        return None, (
            "Tesseract OCR executable was not found or could not run. Install tesseract-ocr "
            "on the server, keep it on PATH, or set TESSERACT_CMD to the executable path. "
            f"Error: {exc}"
        )

    text_parts = []
    failures = []
    for file_info in saved_files:
        if file_info.get("category") != "drug-images":
            continue
        if file_info.get("extension", "").lower() not in ALLOWED_IMAGE_EXTENSIONS:
            continue
        try:
            file_path = os.path.join(UPLOAD_DIR, file_info["relative_path"])
            with Image.open(file_path) as image:
                text_parts.append(
                    pytesseract.image_to_string(
                        image.convert("RGB"),
                        lang=TESSERACT_LANG,
                        config=TESSERACT_CONFIG,
                    )
                )
        except Exception as exc:
            failures.append(f"{file_info.get('original_name')}: {exc}")

    text = "\n".join(part for part in text_parts if part.strip()).strip()
    if not text:
        note = "Local OCR did not extract text from the uploaded drug images."
        if failures:
            note = f"{note} OCR errors: {'; '.join(failures[:3])}"
        return None, note

    note = None
    if failures:
        note = f"Some uploaded drug images could not be read by local OCR: {'; '.join(failures[:3])}"
    return {"observed_text": text, "drug_names": parse_possible_drug_names(text)}, note

def build_label_flags(openfda_results, current_medications, medical_history):
    """Create review flags when openFDA label text mentions patient meds or history terms."""
    combined_context = f"{current_medications}\n{medical_history}".lower()
    context_names = [name.lower() for name in parse_possible_drug_names(current_medications)]
    history_words = {
        word.lower()
        for word in re.findall(r"[A-Za-z][A-Za-z\-]{4,}", medical_history or "")
        if word.lower() not in STOP_MEDICATION_WORDS
    }

    flags = []
    for result in openfda_results:
        if not result.get("found"):
            continue
        label = result.get("label") or {}
        interaction_text = (label.get("drug_interactions") or "").lower()
        warning_text = " ".join([
            label.get("warnings") or "",
            label.get("contraindications") or "",
        ]).lower()

        for name in context_names:
            if name and name != result.get("query", "").lower() and name in interaction_text:
                flags.append({
                    "type": "label_interaction_text_match",
                    "drug": result.get("query"),
                    "matched_context": name,
                    "message": f"The openFDA label interaction section mentions {name}.",
                })

        for word in list(history_words)[:20]:
            if word in warning_text and word in combined_context:
                flags.append({
                    "type": "label_warning_history_text_match",
                    "drug": result.get("query"),
                    "matched_context": word,
                    "message": f"The openFDA warning or contraindication text mentions {word}.",
                })

    return flags[:20]

def clinical_agent_dependencies():
    """Package local helper functions so the external clinical agent module can call them."""
    return {
        "build_label_flags": build_label_flags,
        "clamp_int": clamp_int,
        "get_db_connection": get_db_connection,
        "gemini_api_key": GEMINI_API_KEY,
        "gemini_clinical_model": GEMINI_CLINICAL_MODEL,
        "lookup_openfda_label": lookup_openfda_label,
        "max_lookup_names": MAX_LOOKUP_NAMES,
        "parse_possible_drug_names": parse_possible_drug_names,
        "retrieve_rag_context": build_crewai_clinical_context,
        "safe_json_loads": safe_json_loads,
    }

def build_crewai_clinical_context(query, top_k=6):
    """Retrieve clinical context through the CrewAI RAG tool using the shared knowledge base."""
    return retrieve_clinical_context(
        query,
        api_key=GEMINI_API_KEY,
        model_name=GEMINI_CLINICAL_MODEL,
        top_k=top_k,
    )

def run_full_clinical_pipeline(data, submission_id=None):
    """Run the diagrammed workflow through the core orchestrator."""
    return orchestrate_full_clinical_pipeline(
        data,
        submission_id=submission_id,
        gemini_api_key=GEMINI_API_KEY,
        gemini_research_model=GEMINI_RESEARCH_MODEL,
        gemini_evidence_reviewer_model=GEMINI_EVIDENCE_REVIEWER_MODEL,
        gemini_report_model=GEMINI_REPORT_MODEL,
        clinical_agent_module=clinical_agent_module,
        clinical_agent_dependencies=clinical_agent_dependencies,
        run_lifestyle_agent=run_lifestyle_agent,
        run_research_agent=run_research_agent,
        run_evidence_reviewer_agent=run_evidence_reviewer_agent,
        run_report_agent=run_report_agent,
        build_arabic_pdf_report=build_arabic_pdf_report,
        save_report_pdf=save_report_pdf,
        upload_dir=UPLOAD_DIR,
        storage_backend=STORAGE_BACKEND,
        storage_is_ephemeral=STORAGE_IS_EPHEMERAL,
    )

def init_db():
    """Create the intake_forms SQLite table if it does not already exist."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS intake_forms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT,
            age INTEGER,
            mobile TEXT,
            email TEXT,
            form_data TEXT
        )
    """)
    conn.commit()
    conn.close()

def render_ai_report(pipeline):
    """Render the clinical pipeline result with the frontend AI report partial."""
    final_report = {}
    report_pdf = {}
    if pipeline:
        report_agent = pipeline.get("report_agent", {})
        final_report = report_agent.get("report") or pipeline.get("final_report") or {}
        if final_report and not any(key in final_report for key in ("executive_summary", "patient_snapshot", "report_type")):
            final_report = {}
        report_pdf = pipeline.get("report_pdf") or {}

    return render_template(
        "ai_report.html",
        pipeline=pipeline,
        final_report=final_report,
        report_pdf=report_pdf,
        format_evidence_claims=format_evidence_claims,
    )

def build_ai_summary_points(pipeline, limit=12):
    """Build a concise bullet-point summary from the AI pipeline outputs."""
    if not pipeline:
        return []

    points = []
    seen = set()

    def add_point(text):
        text = str(text or "").strip()
        if not text:
            return
        key = text.lower()
        if key in seen:
            return
        seen.add(key)
        points.append(text)

    def add_list(prefix, values, max_items=2):
        count = 0
        for value in values or []:
            text = str(value or "").strip()
            if not text:
                continue
            add_point(f"{prefix}: {text}" if prefix else text)
            count += 1
            if count >= max_items or len(points) >= limit:
                break

    status = str(pipeline.get("status") or "").strip()
    stopped_after = str(pipeline.get("stopped_after") or "").strip()
    if status:
        add_point(f"Pipeline status: {status}")

    if pipeline.get("error"):
        add_point(f"Pipeline error: {pipeline.get('error')}")

    lifestyle = pipeline.get("lifestyle_agent") or {}
    if lifestyle:
        decision = str(lifestyle.get("decision") or "").strip()
        confidence = str(lifestyle.get("confidence") or "").strip()
        reasoning = str(lifestyle.get("reasoning") or "").strip()
        if decision or confidence:
            label = "Lifestyle triage"
            decision_text = {
                "no": "No concern identified",
                "yes": "Concern identified",
                "likely": "Likely concern identified",
                "unlikely": "Unlikely concern",
            }.get(decision.lower(), decision)
            suffix = f": {decision_text}" if decision_text else ""
            if confidence:
                confidence_text = confidence.lower()
                if confidence_text in {"high", "medium", "low"}:
                    confidence_text = f"{confidence_text.capitalize()} confidence"
                suffix += f" ({confidence_text})" if suffix else f": {confidence_text}"
            add_point(label + suffix)
        if reasoning:
            add_point(f"Lifestyle note: {reasoning}")
        add_list("Lifestyle recommendation", lifestyle.get("lifestyle_recommendations", []), max_items=2)
        add_list("Lifestyle flag", lifestyle.get("flags", []), max_items=2)

    clinical = pipeline.get("clinical_agent") or {}
    clinical_report = (clinical.get("clinical_agent") or {}).get("report") or {}
    if clinical_report:
        add_point(clinical_report.get("clinical_summary"))
        add_list("Clinical finding", clinical_report.get("key_findings", []), max_items=2)
        add_list("Medication safety", clinical_report.get("medication_safety", []), max_items=2)
        add_list("Red flag", clinical_report.get("red_flags", []), max_items=2)

    research = pipeline.get("research_agent") or {}
    research_report = research.get("report") or {}
    if research_report:
        add_point(research_report.get("research_summary"))
        if research.get("pubmed_papers"):
            add_point(f"PubMed papers retrieved: {len(research.get('pubmed_papers') or [])}")
        if research.get("pubmed_error"):
            add_point(f"PubMed error: {research.get('pubmed_error')}")
        add_list("Evidence point", research_report.get("evidence_points", []), max_items=2)
        add_list("Clinical relevance", research_report.get("clinical_relevance", []), max_items=1)

    evidence = pipeline.get("evidence_reviewer_agent") or {}
    evidence_report = evidence.get("report") or {}
    if evidence_report:
        quality = str(evidence_report.get("overall_evidence_quality") or "").strip()
        readiness = str(evidence_report.get("final_report_readiness") or "").strip()
        if quality or readiness:
            add_point(
                "Evidence review"
                + (f": quality {quality}" if quality else "")
                + (f", readiness {readiness}" if readiness else "")
            )
        add_point(evidence_report.get("reviewer_summary"))
        add_list("Reviewer priority", evidence_report.get("clinician_review_priorities", []), max_items=2)
        add_list("Citation issue", evidence_report.get("citation_quality_issues", []), max_items=1)

    report_agent = pipeline.get("report_agent") or {}
    final_report = report_agent.get("report") or pipeline.get("final_report") or {}
    if final_report:
        add_point(final_report.get("executive_summary"))
        report_type = str(final_report.get("report_type") or "").strip()
        confidence = str(final_report.get("confidence") or "").strip()
        if report_type or confidence:
            add_point(
                "Final report"
                + (f": {report_type}" if report_type else "")
                + (f" ({confidence} confidence)" if confidence else "")
            )
        add_list("Urgent alert", final_report.get("urgent_safety_alerts", []), max_items=2)
        add_list("Clinician action", final_report.get("clinician_actions", []), max_items=2)
        add_list("Missing information", final_report.get("missing_information", []), max_items=1)

    return points[:limit]

def format_evidence_claims(items):
    """Convert evidence reviewer claim dictionaries into readable list rows."""
    rows = []
    for item in items or []:
        if not isinstance(item, dict):
            rows.append(str(item))
            continue
        parts = [
            item.get("claim"),
            item.get("support"),
            item.get("quality_reason") or item.get("quality_issue"),
        ]
        rows.append(" | ".join(str(part) for part in parts if part))
    return rows

