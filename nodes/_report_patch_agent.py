"""Patch an existing generated report with doctor-supplied missing information."""

from __future__ import annotations

import json

from core.agent_utils import compact_text
from nodes._report_chat_agent import (
    ReportChatError,
    ReportChatUnavailable,
    load_report_chat_submission,
    normalize_submission_id,
)
from nodes.tasks import get_agent_definition, get_task_definition
from tools.crewai_agent_tools import run_crewai_json_agent
from tools.report_normalization import dedupe_list, normalize_final_report, text_key


GEMINI_REPORT_PATCH_MODEL = "gemini-2.5-flash"
MAX_PATCH_TEXT_CHARS = 6000


def _clean_patch_text(value):
    text = str(value or "").strip()
    if not text:
        raise ReportChatError("filled_information is required.")
    if len(text) > MAX_PATCH_TEXT_CHARS:
        raise ReportChatError(
            f"filled_information must be {MAX_PATCH_TEXT_CHARS} characters or fewer."
        )
    return text


def _resolve_existing_report(submission):
    form_data = submission.get("form_data") or {}
    pipeline = form_data.get("clinical_pipeline") or {}
    status = str(pipeline.get("status") or "").strip().lower()
    if status != "completed":
        raise ReportChatUnavailable("Report generation is not completed for this submission.")

    report_agent = pipeline.get("report_agent") or {}
    report = report_agent.get("report") or pipeline.get("final_report") or {}
    if not isinstance(report, dict) or not report:
        raise ReportChatUnavailable("No generated final report is saved for this submission.")
    return normalize_final_report(report)


def build_report_patch_packet(submission, filled_information, missing_item=""):
    """Build the packet for patching an existing final report only."""
    clean_text = _clean_patch_text(filled_information)
    existing_report = _resolve_existing_report(submission)
    form_data = submission.get("form_data") or {}
    doctor_notes = form_data.get("doctor_report_notes") or []
    if not isinstance(doctor_notes, list):
        doctor_notes = []

    return {
        "submission_id": int(submission["id"]),
        "code_no": submission["code_no"],
        "instruction": (
            "Patch only the existing final report. Keep the report structure, preserve supported content, "
            "and update only the parts affected by the doctor's supplied missing information. "
            "Resolve only target_missing_information_item; leave every other missing item unchanged."
        ),
        "doctor_filled_information": clean_text,
        "target_missing_information_item": str(missing_item or "").strip(),
        "existing_final_report": existing_report,
        "current_missing_information": existing_report.get("missing_information", []),
        "saved_doctor_notes": doctor_notes[-20:],
        "patient_form_context": {
            "weight": form_data.get("weight"),
            "height": form_data.get("height"),
            "bmi": form_data.get("bmi"),
            "waist": form_data.get("waist"),
            "currentMedications": form_data.get("currentMedications"),
            "medicalHistory": form_data.get("medicalHistory"),
            "investigationResults": form_data.get("investigationResults"),
        },
    }


def call_report_patch_agent(packet, *, api_key, model_name=GEMINI_REPORT_PATCH_MODEL, timeout=60):
    """Run a focused report patch agent over an existing saved final report."""
    agent_def = get_agent_definition("report_patch")
    task_def = get_task_definition("report_patch")
    return run_crewai_json_agent(
        role=agent_def["role"],
        goal=agent_def["goal"],
        backstory=agent_def["backstory"],
        task_prompt=(
            f"{task_def['description']}\n\n"
            f"{json.dumps(packet, ensure_ascii=False, indent=2)}"
        ),
        expected_output=task_def["expected_output"],
        api_key=api_key,
        model_name=model_name,
        max_tokens=8192,
        timeout=timeout,
        label="CrewAI report patch agent",
    )


def _keyword_score(text, keywords):
    normalized = text_key(text)
    return sum(1 for keyword in keywords if keyword in normalized)


def _filter_resolved_missing_items(missing_information, patch_text):
    patch_key = text_key(patch_text)
    rules = [
        (("pelvic", "surgery"), ("pelvic surgery", "surgery date", "surgery outcome")),
        (("blood", "pressure"), ("blood pressure", "heart rate", "vital signs")),
        (("bmi",), ("bmi", "body mass index")),
        (("waist",), ("waist", "waist circumference")),
        (("hba1c",), ("hba1c", "glucose", "fasting blood glucose")),
        (("lipid",), ("lipid", "cholesterol", "triglyceride")),
        (("testosterone",), ("testosterone", "total testosterone", "free testosterone")),
        (("medication",), ("current medications", "over the counter", "supplements")),
        (("ed",), ("erectile dysfunction", "ed")),
        (("pe",), ("premature ejaculation", "pe")),
        (("libido",), ("low libido", "libido")),
        (("evaluation",), ("previous evaluations", "previous treatments", "treatments")),
        (("renal",), ("renal function", "renal impairment", "kidney")),
    ]

    remaining = []
    for item in missing_information or []:
        item_score = 0
        for patch_keywords, item_keywords in rules:
            if _keyword_score(item, item_keywords) and any(keyword in patch_key for keyword in patch_keywords):
                item_score += 1
        if item_score:
            continue
        remaining.append(item)
    return dedupe_list(remaining)


def build_fallback_report_patch(packet, error=None):
    """Return a conservative patched report if the patch agent cannot run."""
    existing_report = normalize_final_report(packet.get("existing_final_report") or {})
    patch_text = compact_text(packet.get("doctor_filled_information"), max_chars=2500)

    updated = normalize_final_report(existing_report)
    evidence_summary = list(updated.get("evidence_summary") or [])
    evidence_summary.append(f"Doctor-supplied missing information update: {patch_text}")
    updated["evidence_summary"] = dedupe_list(evidence_summary)

    clinician_actions = list(updated.get("clinician_actions") or [])
    clinician_actions.append("Review the doctor-supplied missing information update that was applied after report generation.")
    updated["clinician_actions"] = dedupe_list(clinician_actions)

    updated["missing_information"] = _filter_resolved_missing_items(
        updated.get("missing_information", []),
        patch_text,
    )

    limitations = list(updated.get("limitations") or [])
    if error:
        limitations.append(
            f"Automatic report patching was unavailable, so a conservative manual patch note was applied instead: {compact_text(error, max_chars=500)}"
        )
    updated["limitations"] = dedupe_list(limitations)
    return updated


def run_report_patch_agent(
    submission_id,
    filled_information,
    dependencies,
    *,
    missing_item="",
    model_name=GEMINI_REPORT_PATCH_MODEL,
):
    """Patch the saved final report for one completed submission."""
    clean_submission_id = normalize_submission_id(submission_id)
    clean_text = _clean_patch_text(filled_information)
    submission = load_report_chat_submission(
        clean_submission_id,
        get_db_connection=dependencies["get_db_connection"],
        safe_json_loads=dependencies["safe_json_loads"],
    )
    packet = build_report_patch_packet(submission, clean_text, missing_item=missing_item)

    existing_report = packet["existing_final_report"]
    target_key = text_key(missing_item)
    if not target_key:
        raise ReportChatError("missing_item is required so exactly one report gap is updated.")
    if not any(text_key(item) == target_key for item in existing_report.get("missing_information", [])):
        raise ReportChatError("The selected missing-information item is no longer present in this report.")
    patient_snapshot_defaults = existing_report.get("patient_snapshot") or {}
    try:
        patched = call_report_patch_agent(
            packet,
            api_key=dependencies.get("gemini_api_key"),
            model_name=model_name,
        )
        llm_error = None
    except RuntimeError as exc:
        patched = build_fallback_report_patch(packet, error=str(exc))
        llm_error = str(exc)

    patched_report = normalize_final_report(patched, patient_snapshot_defaults=patient_snapshot_defaults)
    patched_report["missing_information"] = [
        item for item in existing_report.get("missing_information", [])
        if text_key(item) != target_key
    ]
    patched_report = normalize_final_report(
        patched_report,
        patient_snapshot_defaults=patient_snapshot_defaults,
    )
    return {
        "submission_id": int(submission["id"]),
        "code_no": submission["code_no"],
        "filled_information": clean_text,
        "existing_report": existing_report,
        "patched_report": patched_report,
        "missing_information_before": existing_report.get("missing_information", []),
        "missing_information_after": patched_report.get("missing_information", []),
        "model": model_name,
        "engine": "crewai",
        "error": llm_error,
    }
