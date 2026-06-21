"""Shared helpers for deduplicating and ordering final report content."""

from __future__ import annotations

import copy
import re
import unicodedata


REPORT_SECTION_FIELDS = [
    ("Urgent Safety Alerts", "urgent_safety_alerts"),
    ("Medication Safety", "medication_safety"),
    ("Findings", "findings"),
    ("Clinical Findings", "clinical_findings"),
    ("Evidence Summary", "evidence_summary"),
    ("Clinician Actions", "clinician_actions"),
    ("Missing Information", "missing_information"),
    ("Limitations", "limitations"),
]

REPORT_TYPE_LABELS = {
    "full_clinical_evidence_review": "Clinical Evidence Review",
    "lifestyle_triage": "Lifestyle Triage",
}


def as_list(value):
    """Normalize a value into a list of non-empty strings."""
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item or "").strip()]
    if value in (None, ""):
        return []
    return [str(value).strip()]


def _strip_source_suffix(text):
    """Remove common source/citation suffixes so duplicate concepts compare cleanly."""
    text = str(text or "").strip()
    if not text:
        return ""

    text = re.split(r"\s+\|\s+", text, maxsplit=1)[0].strip()
    text = re.sub(
        r"\s*[\(\[][^()\[\]]*(?:pdf|pmid|doi|p\.\s*\d+|score\s*\d|https?://|source)[^()\[\]]*[\)\]]\s*$",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()
    return text


def text_key(text):
    """Build a normalized comparison key for deduplication."""
    text = _strip_source_suffix(text)
    text = unicodedata.normalize("NFKC", text).casefold()
    text = re.sub(r"[^\w\s]+", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def dedupe_list(values, *, seen=None):
    """Deduplicate a list while preserving order."""
    seen = seen if seen is not None else set()
    unique_values = []
    for item in as_list(values):
        key = text_key(item)
        if not key or key in seen:
            continue
        seen.add(key)
        unique_values.append(item)
    return unique_values


def display_report_type(value):
    """Return a professional display label for an internal report type code."""
    text = str(value or "").strip()
    if not text:
        return ""
    return REPORT_TYPE_LABELS.get(text, text.replace("_", " ").title())


def _join_readiness_parts(parts):
    """Join human-readable readiness gaps with natural punctuation."""
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return f"{parts[0]} and {parts[1]}"
    return f"{', '.join(parts[:-1])}, and {parts[-1]}"


def describe_report_readiness(readiness, missing_evidence=None):
    """Return a clinician-friendly explanation for the evidence reviewer readiness flag."""
    readiness = str(readiness or "").strip().lower()
    if not readiness:
        return ""
    if readiness == "ready":
        return "Ready for clinician review based on the available evidence."
    if readiness == "ready_with_cautions":
        return "Ready for clinician review with cautions; verify flagged uncertainties and missing details."
    if readiness != "not_ready":
        return readiness.replace("_", " ").capitalize()

    combined = " ".join(as_list(missing_evidence)).lower()
    needs_labs = any(
        token in combined
        for token in ("lab", "testosterone", "hba1c", "glucose", "lipid", "prolactin", "lh", "fsh")
    )
    needs_exam = any(
        token in combined
        for token in (
            "physical examination",
            "physical exam",
            "exam",
            "genitourinary",
            "endocrine",
            "vascular",
            "neurological",
            "blood pressure",
            "heart rate",
            "bmi",
            "waist",
        )
    )
    needs_meds = any(
        token in combined
        for token in ("current medications", "complete list of all current medications", "dosages", "medication")
    )
    missing_parts = []
    if needs_labs:
        missing_parts.append("labs")
    if needs_exam:
        missing_parts.append("exam findings")
    if needs_meds:
        missing_parts.append("medication list")
    if missing_parts:
        summary = _join_readiness_parts(missing_parts)
        verb = "is" if len(missing_parts) == 1 else "are"
        return f"Not ready for clinical use until missing {summary} {verb} reviewed."
    return "Not ready for clinical use until the missing patient-specific evidence is reviewed."


def normalize_patient_snapshot(snapshot, defaults=None):
    """Return a normalized patient snapshot while preserving optional identity fields."""
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    defaults = defaults if isinstance(defaults, dict) else {}

    def pick(*keys):
        for source in (snapshot, defaults):
            for key in keys:
                value = source.get(key)
                if value not in (None, ""):
                    return value
        return ""

    return {
        "submission_id": str(pick("submission_id")).strip(),
        "full_name": str(pick("full_name", "name")).strip(),
        "age": str(pick("age")).strip(),
        "sex": str(pick("sex", "gender")).strip(),
        "mobile": str(pick("mobile", "phone")).strip(),
        "email": str(pick("email")).strip(),
        "presenting_question": str(pick("presenting_question")).strip(),
    }


def canonical_report_sections(report):
    """Return non-empty report sections in a stable, deduplicated order."""
    report = report or {}
    seen = set()
    sections = []
    for heading, field_name in REPORT_SECTION_FIELDS:
        items = dedupe_list(report.get(field_name), seen=seen)
        if items:
            sections.append({
                "heading": heading,
                "items": items,
            })
    return sections


def normalize_final_report(report, patient_snapshot_defaults=None):
    """Return a cleaned final report with repeated concepts removed."""
    report = copy.deepcopy(report or {})

    for field in (
        "report_title",
        "report_type",
        "executive_summary",
        "clinical_summary",
        "confidence",
    ):
        if field in report and report.get(field) is not None:
            report[field] = str(report.get(field)).strip()

    if not report.get("report_title"):
        report["report_title"] = "AI Clinical Evidence Report"

    if not report.get("report_type"):
        report["report_type"] = "full_clinical_evidence_review"

    report["patient_snapshot"] = normalize_patient_snapshot(
        report.get("patient_snapshot"),
        defaults=patient_snapshot_defaults,
    )

    list_fields_in_order = [
        "urgent_safety_alerts",
        "medication_safety",
        "findings",
        "clinical_findings",
        "evidence_summary",
        "clinician_actions",
        "missing_information",
        "limitations",
    ]

    seen = set()
    for field_name in list_fields_in_order:
        report[field_name] = dedupe_list(report.get(field_name), seen=seen)

    citations = dedupe_list(report.get("citations"))
    source_citations = dedupe_list(report.get("source_citations"))
    if not citations and source_citations:
        citations = source_citations
    report["citations"] = citations
    report["source_citations"] = []

    report["structured_sections"] = canonical_report_sections(report)

    return report
