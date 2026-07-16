import base64
import hmac
import io
import json
import logging
import mimetypes
import os
import re
import shutil
import sqlite3
import tempfile
import uuid
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode

from flask import Response, render_template, request
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash, generate_password_hash

from core.agent_utils import compact_text as first_text
from core.agent_utils import load_secret as read_secret
from core.agent_utils import gemini_model_resource, gemini_text, parse_json_object, request_json
from core.crew_orchestrator import run_crewai_workflow as orchestrate_full_clinical_pipeline
from core.submission_metadata import build_doctor_report_note, ensure_created_at_column, utc_now_iso
from nodes.RAG_agent import retrieve_clinical_context
import nodes.agents as clinical_agent_module
from nodes.agents import (
    build_arabic_pdf_report,
    save_report_pdf as save_report_pdf_to_disk,
)
from tools.report_normalization import (
    describe_report_readiness,
    display_report_type,
    normalize_final_report,
    text_key,
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

if load_dotenv:
    load_dotenv(os.path.join(BASE_DIR, ".env"), override=False)

LOG_LEVEL = (os.environ.get("LOG_LEVEL") or "INFO").strip().upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("patient_intake.storage")


def env_value(*names, default=""):
    """Read env vars, including markdown-escaped names copied from notes."""
    for name in names:
        candidates = (name, name.replace("_", r"\_"))
        for candidate in candidates:
            value = os.environ.get(candidate)
            if value not in (None, ""):
                return str(value).strip()
    return default


DB_PATH = env_value("DB_PATH") or os.path.join(BASE_DIR, "intake.db")
UPLOAD_DIR = env_value("UPLOAD_DIR") or os.path.join(BASE_DIR, "uploads")
STORAGE_BACKEND = (env_value("STORAGE_BACKEND") or "local_filesystem").strip().lower()
STORAGE_IS_EPHEMERAL = False
AZURE_STORAGE_CONNECTION_STRING = env_value("AZURE_STORAGE_CONNECTION_STRING")
AZURE_ACCOUNT_NAME = env_value("AZURE_ACCOUNT_NAME")
AZURE_ACCOUNT_KEY = env_value("AZURE_ACCOUNT_KEY")
AZURE_STORAGE_CONTAINER = (
    env_value("AZURE_STORAGE_CONTAINER")
    or env_value("AZURE_BLOB_CONTAINER")
    or env_value("AZURE_CONTAINER_NAME")
    or env_value("BLOB_NAME")
    or ""
).strip()
APP_BASE_PATH = env_value("APP_BASE_PATH").strip()
if APP_BASE_PATH and APP_BASE_PATH != "/":
    APP_BASE_PATH = "/" + APP_BASE_PATH.strip("/")
else:
    APP_BASE_PATH = ""


_azure_blob_service_client = None
_azure_container_ready = False


TESSERACT_FALLBACK_PATHS = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    "/usr/bin/tesseract",
    "/usr/local/bin/tesseract",
)


def resolve_tesseract_cmd():
    """Find the Tesseract executable on Windows or Linux."""
    configured = os.environ.get("TESSERACT_CMD", "").strip().strip('"')
    if configured:
        return configured

    path_command = shutil.which("tesseract")
    if path_command:
        return path_command

    for candidate in TESSERACT_FALLBACK_PATHS:
        if os.path.exists(candidate):
            return candidate

    return ""


def deployment_info():
    """Return storage/runtime metadata useful for deployed clients and admin routes."""
    return {
        "platform": "local",
        "storage_backend": STORAGE_BACKEND,
        "storage_ephemeral": STORAGE_IS_EPHEMERAL,
        "database_path": DB_PATH,
        "upload_dir": UPLOAD_DIR,
        "azure_container": AZURE_STORAGE_CONTAINER if is_azure_storage_enabled() else "",
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


def is_azure_storage_enabled():
    """Return True when uploaded files should be stored in Azure Blob Storage."""
    return STORAGE_BACKEND in {"azure", "azure_blob", "azure-blob", "blob"}


def _yes_no(value):
    return "yes" if bool(value) else "no"


def _normalize_blob_name(relative_path):
    blob_name = str(relative_path or "").replace("\\", "/").lstrip("/")
    if not blob_name or blob_name.startswith("../") or "/../" in f"/{blob_name}":
        raise ValueError("Invalid upload path.")
    return blob_name


def _clean_azure_connection_string(value):
    """Normalize common copy/paste artifacts from credential notes."""
    value = str(value or "").strip().strip("\"'")
    value = value.replace("[EndpointSuffix=core.windows.net](http://EndpointSuffix=core.windows.net)", "EndpointSuffix=core.windows.net")
    value = value.replace("[EndpointSuffix=core.windows.net](https://EndpointSuffix=core.windows.net)", "EndpointSuffix=core.windows.net")
    return value


def _azure_service_client():
    """Create the Azure Blob client lazily so local storage works without Azure packages."""
    global _azure_blob_service_client
    if _azure_blob_service_client is not None:
        return _azure_blob_service_client

    try:
        from azure.storage.blob import BlobServiceClient
    except ImportError as exc:
        raise RuntimeError("azure-storage-blob is not installed. Run python -m pip install -e .") from exc

    connection_string = _clean_azure_connection_string(AZURE_STORAGE_CONNECTION_STRING)
    if connection_string:
        logger.info(
            "[storage] creating Azure BlobServiceClient from connection string "
            "account_configured=%s container=%s",
            _yes_no(True),
            AZURE_STORAGE_CONTAINER or "(missing)",
        )
        _azure_blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        return _azure_blob_service_client

    if AZURE_ACCOUNT_NAME and AZURE_ACCOUNT_KEY:
        account_url = f"https://{AZURE_ACCOUNT_NAME}.blob.core.windows.net"
        logger.info(
            "[storage] creating Azure BlobServiceClient from account credentials "
            "account=%s container=%s key_configured=%s",
            AZURE_ACCOUNT_NAME,
            AZURE_STORAGE_CONTAINER or "(missing)",
            _yes_no(AZURE_ACCOUNT_KEY),
        )
        _azure_blob_service_client = BlobServiceClient(account_url=account_url, credential=AZURE_ACCOUNT_KEY)
        return _azure_blob_service_client

    raise RuntimeError(
        "Azure Blob Storage is enabled but credentials are missing. Set "
        "AZURE_STORAGE_CONNECTION_STRING or AZURE_ACCOUNT_NAME/AZURE_ACCOUNT_KEY."
    )


def _azure_container_client():
    """Return a container client and create the container if needed."""
    global _azure_container_ready
    if not AZURE_STORAGE_CONTAINER:
        raise RuntimeError("Azure Blob Storage is enabled but AZURE_STORAGE_CONTAINER is not configured.")

    container_client = _azure_service_client().get_container_client(AZURE_STORAGE_CONTAINER)
    if not _azure_container_ready:
        try:
            container_client.create_container()
            logger.info("[storage] Azure container created container=%s", AZURE_STORAGE_CONTAINER)
        except Exception as exc:
            if exc.__class__.__name__ not in {"ResourceExistsError", "ContainerAlreadyExists"}:
                logger.exception(
                    "[storage] Azure container setup failed container=%s error_type=%s",
                    AZURE_STORAGE_CONTAINER,
                    exc.__class__.__name__,
                )
                raise
            logger.info("[storage] Azure container exists container=%s", AZURE_STORAGE_CONTAINER)
        _azure_container_ready = True
    return container_client


def upload_storage_bytes(relative_path, contents, *, content_type="application/octet-stream"):
    """Store upload bytes in the configured backend."""
    blob_name = _normalize_blob_name(relative_path)
    content_type = content_type or mimetypes.guess_type(blob_name)[0] or "application/octet-stream"
    byte_count = len(contents or b"")

    logger.info(
        "[storage] upload requested backend=%s azure_enabled=%s blob=%s bytes=%s content_type=%s container=%s",
        STORAGE_BACKEND,
        _yes_no(is_azure_storage_enabled()),
        blob_name,
        byte_count,
        content_type,
        AZURE_STORAGE_CONTAINER or "(none)",
    )

    if is_azure_storage_enabled():
        try:
            from azure.storage.blob import ContentSettings
        except ImportError as exc:
            raise RuntimeError("azure-storage-blob is not installed. Run python -m pip install -e .") from exc

        try:
            blob_client = _azure_container_client().get_blob_client(blob_name)
            blob_client.upload_blob(
                contents,
                overwrite=True,
                content_settings=ContentSettings(content_type=content_type),
            )
        except Exception as exc:
            logger.exception(
                "[storage] Azure upload failed container=%s blob=%s bytes=%s error_type=%s",
                AZURE_STORAGE_CONTAINER or "(missing)",
                blob_name,
                byte_count,
                exc.__class__.__name__,
            )
            raise RuntimeError(f"Azure Blob upload failed for {blob_name}: {exc}") from exc
        logger.info(
            "[storage] Azure upload succeeded container=%s blob=%s bytes=%s",
            AZURE_STORAGE_CONTAINER,
            blob_name,
            byte_count,
        )
        return

    destination_path = os.path.join(UPLOAD_DIR, blob_name)
    os.makedirs(os.path.dirname(destination_path), exist_ok=True)
    with open(destination_path, "wb") as file_obj:
        file_obj.write(contents)
    logger.info("[storage] local upload saved path=%s bytes=%s", destination_path, byte_count)


def read_storage_bytes(relative_path):
    """Read upload bytes from the configured backend."""
    blob_name = _normalize_blob_name(relative_path)
    local_path = os.path.join(UPLOAD_DIR, blob_name)
    logger.info(
        "[storage] read requested backend=%s azure_enabled=%s blob=%s container=%s",
        STORAGE_BACKEND,
        _yes_no(is_azure_storage_enabled()),
        blob_name,
        AZURE_STORAGE_CONTAINER or "(none)",
    )
    if is_azure_storage_enabled():
        try:
            blob_client = _azure_container_client().get_blob_client(blob_name)
            data = blob_client.download_blob().readall()
            logger.info("[storage] Azure read succeeded blob=%s bytes=%s", blob_name, len(data or b""))
            return data
        except Exception as exc:
            logger.exception(
                "[storage] Azure read failed blob=%s error_type=%s fallback_local_exists=%s",
                blob_name,
                exc.__class__.__name__,
                _yes_no(os.path.exists(local_path)),
            )
            if os.path.exists(local_path):
                with open(local_path, "rb") as file_obj:
                    return file_obj.read()
            raise

    with open(local_path, "rb") as file_obj:
        return file_obj.read()


def storage_file_exists(relative_path):
    """Return whether an upload exists in the configured backend."""
    try:
        blob_name = _normalize_blob_name(relative_path)
    except ValueError:
        return False

    if is_azure_storage_enabled():
        try:
            if _azure_container_client().get_blob_client(blob_name).exists():
                return True
        except Exception:
            pass

    return os.path.exists(os.path.join(UPLOAD_DIR, blob_name))


def storage_content_type(relative_path, fallback="application/octet-stream"):
    """Guess an upload's MIME type from its path."""
    return mimetypes.guess_type(str(relative_path or ""))[0] or fallback


def storage_status(check_remote=False):
    """Return safe storage diagnostics without exposing secrets."""
    status = {
        "backend": STORAGE_BACKEND,
        "azure_enabled": is_azure_storage_enabled(),
        "container": AZURE_STORAGE_CONTAINER,
        "has_connection_string": bool(AZURE_STORAGE_CONNECTION_STRING),
        "has_account_name": bool(AZURE_ACCOUNT_NAME),
        "has_account_key": bool(AZURE_ACCOUNT_KEY),
        "upload_dir": UPLOAD_DIR,
    }
    if check_remote and is_azure_storage_enabled():
        try:
            container_client = _azure_container_client()
            status["remote_check"] = "ok"
            status["container_exists"] = bool(container_client.exists())
        except Exception as exc:
            status["remote_check"] = "error"
            status["remote_error_type"] = exc.__class__.__name__
            status["remote_error"] = str(exc)
    return status


def log_storage_configuration():
    status = storage_status(check_remote=False)
    logger.info(
        "[storage] configured backend=%s azure_enabled=%s container=%s "
        "connection_string=%s account_name=%s account_key=%s upload_dir=%s",
        status["backend"],
        _yes_no(status["azure_enabled"]),
        status["container"] or "(none)",
        _yes_no(status["has_connection_string"]),
        _yes_no(status["has_account_name"]),
        _yes_no(status["has_account_key"]),
        status["upload_dir"],
    )
    if status["azure_enabled"] and not status["container"]:
        logger.error("[storage] Azure backend enabled but container is missing.")
    if status["azure_enabled"] and not (status["has_connection_string"] or (status["has_account_name"] and status["has_account_key"])):
        logger.error("[storage] Azure backend enabled but credentials are missing.")


log_storage_configuration()

SUBMISSIONS_PASSWORD = os.environ.get("SUBMISSIONS_PASSWORD", "Doctor")
OPENFDA_API_KEY = load_secret("OPENFDA_API_KEY")
DRUGBANK_API_KEY = load_secret("DRUGBANK_API_KEY")
DRUGBANK_REGION = os.environ.get("DRUGBANK_REGION", "us")
GEMINI_API_KEY = load_secret("GEMINI_API_KEY")
GEMINI_CLINICAL_MODEL = os.environ.get("GEMINI_CLINICAL_MODEL", "gemini-2.5-flash")
GEMINI_RESEARCH_MODEL = os.environ.get("GEMINI_RESEARCH_MODEL", "gemini-2.5-flash")
GEMINI_EVIDENCE_REVIEWER_MODEL = os.environ.get("GEMINI_EVIDENCE_REVIEWER_MODEL", "gemini-2.5-flash")
GEMINI_REPORT_MODEL = os.environ.get("GEMINI_REPORT_MODEL", "gemini-2.5-flash")
GEMINI_REPORT_CHAT_MODEL = os.environ.get("GEMINI_REPORT_CHAT_MODEL", GEMINI_REPORT_MODEL)
GEMINI_REPORT_PATCH_MODEL = os.environ.get("GEMINI_REPORT_PATCH_MODEL", GEMINI_REPORT_MODEL)
GEMINI_OCR_MODEL = os.environ.get("GEMINI_OCR_MODEL", "gemini-3.5-flash")
TESSERACT_CMD = resolve_tesseract_cmd()
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
    ensure_report_chat_schema(conn)
    return conn


def ensure_intake_form_schema(conn):
    """Add optional intake form columns that newer app versions rely on."""
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(intake_forms)")
    existing_columns = {row[1] for row in cur.fetchall()}

    if "patient_password_hash" not in existing_columns:
        cur.execute("ALTER TABLE intake_forms ADD COLUMN patient_password_hash TEXT")
        conn.commit()
    ensure_created_at_column(conn)

def ensure_report_chat_schema(conn):
    """Create the report-specific chat audit table when needed."""
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS report_chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            submission_id INTEGER NOT NULL,
            code_no TEXT,
            question TEXT NOT NULL,
            answer_json TEXT NOT NULL,
            answer_text TEXT,
            model TEXT,
            context_hash TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(submission_id) REFERENCES intake_forms(id)
        )
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_report_chat_messages_submission_created
        ON report_chat_messages(submission_id, created_at, id)
    """)
    conn.commit()

def save_report_chat_message(submission_id, question, answer, *, model="", context_hash=""):
    """Persist one doctor/report chat exchange for audit history."""
    created_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    submission_id = int(submission_id)
    code_no = f"INT-{submission_id}"
    answer_json = json.dumps(answer or {}, ensure_ascii=False)
    answer_text = ""
    if isinstance(answer, dict):
        answer_text = str(answer.get("direct_answer") or "")

    conn = get_db_connection()
    try:
        cur = conn.execute(
            """
            INSERT INTO report_chat_messages
                (submission_id, code_no, question, answer_json, answer_text, model, context_hash, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                submission_id,
                code_no,
                str(question or ""),
                answer_json,
                answer_text,
                str(model or ""),
                str(context_hash or ""),
                created_at,
            ),
        )
        conn.commit()
        chat_id = cur.lastrowid
    finally:
        conn.close()

    return {
        "id": chat_id,
        "submission_id": submission_id,
        "code_no": code_no,
        "question": str(question or ""),
        "answer": answer or {},
        "model": str(model or ""),
        "context_hash": str(context_hash or ""),
        "created_at": created_at,
    }

def list_report_chat_history(submission_id, limit=50):
    """Return saved report chat exchanges for one submission only."""
    submission_id = int(submission_id)
    limit = clamp_int(limit, 50, 1, 200)
    conn = get_db_connection()
    try:
        rows = conn.execute(
            """
            SELECT id, submission_id, code_no, question, answer_json, answer_text, model, context_hash, created_at
            FROM report_chat_messages
            WHERE submission_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (submission_id, limit),
        ).fetchall()
    finally:
        conn.close()

    history = []
    for row in reversed(rows):
        history.append({
            "id": row["id"],
            "submission_id": row["submission_id"],
            "code_no": row["code_no"] or f"INT-{row['submission_id']}",
            "question": row["question"] or "",
            "answer": safe_json_loads(row["answer_json"], {}),
            "answer_text": row["answer_text"] or "",
            "model": row["model"] or "",
            "context_hash": row["context_hash"] or "",
            "created_at": row["created_at"] or "",
        })
    return history

def save_doctor_report_note(submission_id, note, *, author="doctor"):
    """Persist a doctor-authored note into the selected submission's report context."""
    submission_id = int(submission_id)
    note_entry = build_doctor_report_note(note, author=author)
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT form_data FROM intake_forms WHERE id = ?",
            (submission_id,),
        ).fetchone()
        if not row:
            raise LookupError(f"Submission INT-{submission_id} was not found.")

        form_data = safe_json_loads(row["form_data"], {})
        notes = form_data.get("doctor_report_notes")
        if not isinstance(notes, list):
            notes = []
        notes.append(note_entry)
        form_data["doctor_report_notes"] = notes
        conn.execute(
            "UPDATE intake_forms SET form_data = ? WHERE id = ?",
            (json.dumps(form_data, ensure_ascii=False), submission_id),
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "submission_id": submission_id,
        "code_no": f"INT-{submission_id}",
        "note": note_entry,
    }

def save_report_patch_result(
    submission_id,
    patched_report,
    *,
    filled_information,
    model="",
    engine="crewai",
    error="",
):
    """Persist a patched final report without rerunning the upstream clinical workflow."""
    submission_id = int(submission_id)
    code_no = f"INT-{submission_id}"
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
        if not row:
            raise LookupError(f"Submission {code_no} was not found.")

        form_data = safe_json_loads(row["form_data"], {})
        pipeline = form_data.get("clinical_pipeline") or {}
        report_agent = pipeline.get("report_agent") or {}
        report_pdf = pipeline.get("report_pdf") or {}
        patient_snapshot_defaults = {
            "submission_id": submission_id,
            "full_name": row["full_name"] or "",
            "age": row["age"] or "",
            "mobile": row["mobile"] or "",
            "email": row["email"] or "",
        }
        normalized_report = normalize_final_report(
            patched_report,
            patient_snapshot_defaults=patient_snapshot_defaults,
        )

        pdf_error = ""
        try:
            report_pdf = save_report_pdf(
                normalized_report,
                upload_dir=UPLOAD_DIR,
                submission_id=submission_id,
                patient_name=row["full_name"] or "",
                code_no=code_no,
                arabic=False,
            )
        except Exception as exc:
            pdf_error = str(exc)
            report_pdf = dict(report_pdf)
            report_pdf["error"] = pdf_error

        created_at = utc_now_iso()
        patch_history = form_data.get("report_patch_history")
        if not isinstance(patch_history, list):
            patch_history = []
        patch_history.append({
            "id": created_at,
            "created_at": created_at,
            "filled_information": str(filled_information or ""),
            "model": str(model or ""),
            "engine": str(engine or ""),
            "error": str(error or ""),
            "pdf_error": pdf_error,
            "missing_information_remaining": normalized_report.get("missing_information", []),
        })

        report_agent["report"] = normalized_report
        report_agent["patched_at"] = created_at
        report_agent["patched_model"] = str(model or "")
        report_agent["patched_engine"] = str(engine or "")
        if error:
            report_agent["patch_error"] = str(error)
        pipeline["report_agent"] = report_agent
        pipeline["final_report"] = normalized_report
        pipeline["report_pdf"] = report_pdf
        form_data["clinical_pipeline"] = pipeline
        form_data["report_patch_history"] = patch_history

        conn.execute(
            "UPDATE intake_forms SET form_data = ? WHERE id = ?",
            (json.dumps(form_data, ensure_ascii=False), submission_id),
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "submission_id": submission_id,
        "code_no": code_no,
        "report": normalized_report,
        "pipeline": pipeline,
        "report_pdf": report_pdf,
        "patch_entry": patch_history[-1],
    }

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
            prefix = f"{APP_BASE_PATH}/uploads/" if APP_BASE_PATH else "/uploads/"
            links.append({
                "url": url if url.startswith(prefix) or url.startswith("/uploads/") else "",
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
    relative_path_normalized = relative_path.replace(os.sep, "/")
    contents = file_obj.read()
    content_type = file_obj.mimetype or mimetypes.guess_type(original_name)[0] or "application/octet-stream"
    upload_storage_bytes(relative_path_normalized, contents, content_type=content_type)
    logger.info(
        "[upload] stored category=%s extension=%s bytes=%s backend=%s relative_path=%s azure_container=%s",
        category,
        ext,
        len(contents),
        STORAGE_BACKEND,
        relative_path_normalized,
        AZURE_STORAGE_CONTAINER if is_azure_storage_enabled() else "",
    )

    return {
        "category": category,
        "original_name": original_name,
        "stored_name": stored_name,
        "relative_path": relative_path_normalized,
        "url": public_upload_url(relative_path),
        "size": len(contents),
        "content_type": content_type,
        "extension": ext,
        "saved_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "storage_backend": STORAGE_BACKEND,
        "ephemeral": STORAGE_IS_EPHEMERAL,
        "blob_container": AZURE_STORAGE_CONTAINER if is_azure_storage_enabled() else "",
        "blob_name": relative_path_normalized if is_azure_storage_enabled() else "",
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

def has_useful_ocr_text(scan):
    """Return True when an OCR result has enough readable text to trust."""
    if not isinstance(scan, dict):
        return False
    text = f"{scan.get('observed_text') or ''}\n{scan.get('image_description') or ''}"
    return sum(1 for char in text if char.isalnum()) >= 3

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
        fallback_paths = ", ".join(TESSERACT_FALLBACK_PATHS)
        return None, (
            "Tesseract OCR executable was not found or could not run. Install tesseract-ocr "
            "on the server, keep it on PATH, or set TESSERACT_CMD to the executable path. "
            f"Checked fallback paths: {fallback_paths}. "
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
            image_bytes = read_storage_bytes(file_info["relative_path"])
            with Image.open(io.BytesIO(image_bytes)) as image:
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

def encode_image_for_gemini(image_bytes):
    """Convert any accepted upload image into a Gemini-compatible JPEG part."""
    from PIL import Image

    with Image.open(io.BytesIO(image_bytes)) as image:
        image.thumbnail((1600, 1600))
        if image.mode in {"RGBA", "LA"}:
            background = Image.new("RGB", image.size, "white")
            alpha = image.getchannel("A")
            background.paste(image, mask=alpha)
            image = background
        else:
            image = image.convert("RGB")

        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=90)

    return {
        "inline_data": {
            "mime_type": "image/jpeg",
            "data": base64.b64encode(buffer.getvalue()).decode("ascii"),
        }
    }

def extract_text_with_gemini(saved_files):
    """Use Gemini vision when local OCR cannot extract useful medication text."""
    if not GEMINI_API_KEY:
        return None, "Gemini OCR fallback is not configured. Set GEMINI_API_KEY to enable image fallback."

    image_parts = []
    failures = []
    for file_info in saved_files:
        if file_info.get("category") != "drug-images":
            continue
        if file_info.get("extension", "").lower() not in ALLOWED_IMAGE_EXTENSIONS:
            continue
        try:
            image_bytes = read_storage_bytes(file_info["relative_path"])
            image_parts.append(encode_image_for_gemini(image_bytes))
        except Exception as exc:
            failures.append(f"{file_info.get('original_name')}: {exc}")

    if not image_parts:
        note = "Gemini OCR fallback did not receive a readable drug image."
        if failures:
            note = f"{note} Image errors: {'; '.join(failures[:3])}"
        return None, note

    prompt = (
        "Local OCR did not extract useful text from these drug or package images. "
        "Inspect the images and return JSON only with these keys: "
        "drug_names (array of visible medication names), observed_text (string with exact visible label text), "
        "image_description (short description of the package, pill, or label), strengths (array), "
        "dosage_forms (array), manufacturer_or_ndc (array), confidence_notes (string). "
        "Do not diagnose, prescribe, or infer medication details that are not visible."
    )
    body = {
        "contents": [{
            "role": "user",
            "parts": [{"text": prompt}] + image_parts,
        }],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 2048,
            "responseMimeType": "application/json",
        },
    }
    url = (
        "https://generativelanguage.googleapis.com/v1beta/"
        f"{gemini_model_resource(GEMINI_OCR_MODEL)}:generateContent?key={GEMINI_API_KEY}"
    )

    try:
        payload = request_json(url, method="POST", body=body, timeout=45)
        text = gemini_text(payload)
        scan = parse_json_object(text, fallback={}) or {"observed_text": text}
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, RuntimeError) as exc:
        return None, f"Gemini OCR fallback failed: {exc}"

    if not has_useful_ocr_text(scan):
        return None, "Gemini OCR fallback did not extract useful text from the uploaded drug images."

    note = f"Local OCR did not return useful text, so Gemini fallback used {GEMINI_OCR_MODEL}."
    if failures:
        note = f"{note} Some images could not be prepared: {'; '.join(failures[:3])}"
    return scan, note

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

def report_chat_dependencies():
    """Package shared helpers for the report chat agent entrypoint."""
    return {
        "get_db_connection": get_db_connection,
        "safe_json_loads": safe_json_loads,
        "gemini_api_key": GEMINI_API_KEY,
        "gemini_report_chat_model": GEMINI_REPORT_CHAT_MODEL,
        "gemini_report_patch_model": GEMINI_REPORT_PATCH_MODEL,
        "retrieve_guideline_context": build_crewai_clinical_context,
    }

def build_crewai_clinical_context(query, top_k=6):
    """Retrieve clinical context through the CrewAI RAG tool using the shared knowledge base."""
    return retrieve_clinical_context(
        query,
        api_key=GEMINI_API_KEY,
        model_name=GEMINI_CLINICAL_MODEL,
        top_k=top_k,
    )


def save_report_pdf(report, *, upload_dir, submission_id=None, patient_name=None, code_no=None, arabic=False):
    """Save a generated report PDF through the configured upload storage backend."""
    if not is_azure_storage_enabled():
        return save_report_pdf_to_disk(
            report,
            upload_dir=upload_dir,
            submission_id=submission_id,
            patient_name=patient_name,
            code_no=code_no,
            arabic=arabic,
        )

    with tempfile.TemporaryDirectory() as temp_upload_dir:
        metadata = save_report_pdf_to_disk(
            report,
            upload_dir=temp_upload_dir,
            submission_id=submission_id,
            patient_name=patient_name,
            code_no=code_no,
            arabic=arabic,
        )
        relative_path = metadata["relative_path"]
        temp_path = os.path.join(temp_upload_dir, relative_path)
        with open(temp_path, "rb") as file_obj:
            upload_storage_bytes(relative_path, file_obj.read(), content_type="application/pdf")

    metadata["storage_backend"] = STORAGE_BACKEND
    metadata["ephemeral"] = STORAGE_IS_EPHEMERAL
    metadata["blob_container"] = AZURE_STORAGE_CONTAINER
    metadata["blob_name"] = metadata["relative_path"]
    return metadata


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
        run_lifestyle_agent=clinical_agent_module.run_lifestyle_agent,
        run_research_agent=clinical_agent_module.run_research_agent,
        run_evidence_reviewer_agent=clinical_agent_module.run_evidence_reviewer_agent,
        run_report_agent=clinical_agent_module.run_report_agent,
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
        status = str(pipeline.get("status") or "").strip().lower()
        report_agent = pipeline.get("report_agent", {})
        final_report = report_agent.get("report") or pipeline.get("final_report") or {}
        if status in {"running", "started", "processing"}:
            final_report = {}
        elif final_report and not any(key in final_report for key in ("executive_summary", "patient_snapshot", "report_type")):
            final_report = {}
        else:
            final_report = normalize_final_report(final_report)
        report_pdf = pipeline.get("report_pdf") or {}

    return render_template(
        "ai_report.html",
        pipeline=pipeline,
        final_report=final_report,
        report_pdf=report_pdf,
        describe_report_readiness=describe_report_readiness,
        display_report_type=display_report_type,
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
        key = text_key(text)
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

    status = str(pipeline.get("status") or "").strip().lower()
    stopped_after = str(pipeline.get("stopped_after") or "").strip()
    if status:
        if status in {"running", "started", "processing"}:
            return ["Pipeline is running."]
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
                "no": "Lifestyle factors not sufficient",
                "yes": "Lifestyle factors likely primary",
                "likely": "Likely lifestyle-related",
                "unlikely": "Unlikely lifestyle-only",
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
        final_report = normalize_final_report(final_report)
        add_point(final_report.get("executive_summary"))
        report_type = str(final_report.get("report_type") or "").strip()
        confidence = str(final_report.get("confidence") or "").strip()
        if report_type or confidence:
            add_point(
                "Final report"
                + (f": {display_report_type(report_type)}" if report_type else "")
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

