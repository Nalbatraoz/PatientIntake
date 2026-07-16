"""Shared submission metadata and clinical measurement helpers."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo


DEFAULT_DISPLAY_TIMEZONE = "Africa/Cairo"


def utc_now_iso():
    """Return a compact UTC timestamp suitable for SQLite and JSON payloads."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def ensure_created_at_column(conn):
    """Ensure intake submissions can store the creation time independently of form JSON."""
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(intake_forms)")
    existing_columns = {row[1] for row in cur.fetchall()}
    if "created_at" not in existing_columns:
        cur.execute("ALTER TABLE intake_forms ADD COLUMN created_at TEXT")
        cur.execute("UPDATE intake_forms SET created_at = COALESCE(created_at, '')")
        conn.commit()


def parse_iso_datetime(value):
    """Parse the app's ISO timestamps and return a timezone-aware datetime when possible."""
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def created_at_value(row_created_at, form_data=None):
    """Resolve the best available creation timestamp for a submission."""
    if row_created_at:
        return str(row_created_at)
    form_data = form_data or {}
    for key in ("created_at", "submitted_at", "submissionCreatedAt"):
        if form_data.get(key):
            return str(form_data[key])
    return ""


def format_created_at(value, timezone_name=DEFAULT_DISPLAY_TIMEZONE):
    """Format a creation timestamp for the submissions page."""
    parsed = parse_iso_datetime(value)
    if not parsed:
        return "Unknown"
    used_system_timezone = False
    try:
        display_tz = ZoneInfo(timezone_name or DEFAULT_DISPLAY_TIMEZONE)
    except Exception:
        # Windows installations may not include the IANA tzdata database. The
        # app server is configured for Cairo, so its local timezone is the
        # accurate fallback and avoids incorrectly labelling local time as UTC.
        display_tz = None
        used_system_timezone = True
    local_dt = parsed.astimezone() if used_system_timezone else parsed.astimezone(display_tz)
    zone_label = local_dt.tzname() or ""
    if used_system_timezone and not zone_label.isascii():
        offset = local_dt.strftime("%z")
        zone_label = f"UTC{offset[:3]}:{offset[3:]}" if offset else "Local"
    return f"{local_dt.strftime('%Y-%m-%d %H:%M')} {zone_label}".strip()


def _first_number(value):
    match = re.search(r"-?\d+(?:\.\d+)?", str(value or ""))
    if not match:
        return None
    try:
        number = float(match.group(0))
    except ValueError:
        return None
    return number if number > 0 else None


def weight_to_kg(value):
    """Parse a weight string, accepting kg by default and lb/lbs when stated."""
    number = _first_number(value)
    if number is None:
        return None
    text = str(value or "").lower()
    if re.search(r"\b(lb|lbs|pound|pounds)\b", text):
        return number * 0.45359237
    return number


def height_to_m(value):
    """Parse a height string, accepting cm by default for values over 3."""
    number = _first_number(value)
    if number is None:
        return None
    text = str(value or "").lower()
    if re.search(r"\b(in|inch|inches)\b", text):
        return number * 0.0254
    if re.search(r"\b(cm|centimeter|centimeters)\b", text):
        return number / 100
    if re.search(r"\b(m|meter|meters)\b", text) and number <= 3:
        return number
    return number / 100 if number > 3 else number


def calculate_bmi(weight, height):
    """Calculate BMI as kg / m^2 and return a one-decimal string."""
    kg = weight_to_kg(weight)
    meters = height_to_m(height)
    if kg is None or meters is None or meters <= 0:
        return ""
    bmi = kg / (meters * meters)
    if bmi <= 0 or bmi > 100:
        return ""
    return f"{bmi:.1f}"


def normalize_bmi_fields(form_data):
    """Populate BMI from weight and height when possible, preserving explicit values."""
    data = dict(form_data or {})
    calculated = calculate_bmi(data.get("weight"), data.get("height"))
    if calculated:
        data["bmi"] = calculated
        data["bmi_formula"] = "BMI = weight(kg) / height(m)^2"
    return data


def build_doctor_report_note(note, *, author="doctor"):
    """Create a normalized doctor note entry for saved report context."""
    text = str(note or "").strip()
    if not text:
        raise ValueError("note is required.")
    if len(text) > 4000:
        raise ValueError("note must be 4000 characters or fewer.")
    return {
        "id": utc_now_iso(),
        "author": str(author or "doctor"),
        "note": text,
        "created_at": utc_now_iso(),
    }
