"""Report-specific CrewAI chat agent."""

from __future__ import annotations

import hashlib
import json
import re

from core.agent_utils import compact_text
from nodes.tasks import get_agent_definition, get_task_definition
from tools.crewai_agent_tools import run_crewai_json_hierarchical_crew


GEMINI_REPORT_CHAT_MODEL = "gemini-2.5-flash"
MAX_QUESTION_CHARS = 2000
MAX_CONTEXT_STRING_CHARS = 6000
MAX_CONTEXT_JSON_CHARS = 90000

SOURCE_DISPLAY_NAMES = {
    "lifestyle_assessment": "Lifestyle Assessment",
    "clinical_review": "Clinical Review",
    "research_review": "Research Review",
    "evidence_quality_review": "Evidence Quality Review",
    "final_clinical_report": "Final Clinical Report",
    "generated_report_packet": "Generated Report Packet",
    "medication_image_ocr": "Medication Image OCR",
    "uploaded_document_review": "Uploaded Document Review",
    "doctor_report_notes": "Doctor Report Notes",
    "question_guidelines": "Retrieved Guidelines",
    "saved_clinical_record": "Saved Clinical Record",
}

REPORT_CHAT_AGENT_NAMES = (
    "report_chat",
    "report_chat_lifestyle",
    "report_chat_clinical",
    "report_chat_research",
    "report_chat_evidence",
    "report_chat_report",
    "report_chat_documents",
    "report_chat_guidelines",
)


class ReportChatError(ValueError):
    """Raised when the report chat request is invalid."""


class ReportChatNotFound(LookupError):
    """Raised when the selected submission cannot be found."""


class ReportChatUnavailable(RuntimeError):
    """Raised when a report is not ready for chat."""


def normalize_submission_id(value):
    """Normalize numeric ids and INT-prefixed patient codes to an integer id."""
    if isinstance(value, int):
        if value > 0:
            return value
        raise ReportChatError("submission_id must be a positive integer.")

    text = str(value or "").strip().upper()
    match = re.fullmatch(r"(?:INT[-\s]*)?(\d+)", text)
    if not match:
        raise ReportChatError("submission_id must be a number or code like INT-1.")

    submission_id = int(match.group(1))
    return submission_id


def _clean_question(question):
    text = str(question or "").strip()
    if not text:
        raise ReportChatError("question is required.")
    if len(text) > MAX_QUESTION_CHARS:
        raise ReportChatError(f"question must be {MAX_QUESTION_CHARS} characters or fewer.")
    return text


def _maybe_json_value(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _compact_for_prompt(value):
    if isinstance(value, dict):
        return {str(key): _compact_for_prompt(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_compact_for_prompt(item) for item in value]
    if isinstance(value, str):
        return compact_text(value, max_chars=MAX_CONTEXT_STRING_CHARS)
    return value


def _json_size(value):
    return len(json.dumps(value, ensure_ascii=False, sort_keys=True))


def _context_hash(saved_evidence):
    payload = json.dumps(saved_evidence or {}, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _compact_uploaded_files(uploaded_files):
    compacted = []
    for item in (uploaded_files or [])[:12]:
        if not isinstance(item, dict):
            continue
        compacted.append({
            "category": item.get("category"),
            "original_name": item.get("original_name") or item.get("name") or item.get("stored_name"),
            "content_type": item.get("content_type"),
            "relative_path": item.get("relative_path"),
            "url": item.get("url"),
            "saved_at": item.get("saved_at"),
        })
    return compacted


def _compact_lifestyle_agent(agent_result):
    if not isinstance(agent_result, dict):
        return {}
    return {
        "decision": agent_result.get("decision"),
        "confidence": agent_result.get("confidence"),
        "dominant_factors": agent_result.get("dominant_factors") or [],
        "reasoning": agent_result.get("reasoning"),
        "lifestyle_recommendations": agent_result.get("lifestyle_recommendations") or [],
        "flags": agent_result.get("flags") or [],
        "proceed_to_pipeline": agent_result.get("proceed_to_pipeline"),
        "error": agent_result.get("error"),
    }


def _compact_clinical_agent(agent_result):
    if not isinstance(agent_result, dict):
        return {}
    rag = agent_result.get("rag") or {}
    clinical_agent = agent_result.get("clinical_agent") or {}
    return {
        "message": agent_result.get("message"),
        "input": agent_result.get("input") or {},
        "clinical_agent": {
            "engine": clinical_agent.get("engine"),
            "model": clinical_agent.get("model"),
            "error": clinical_agent.get("error"),
            "report": clinical_agent.get("report") or {},
        },
        "rag": {
            "query": rag.get("query"),
            "sources": rag.get("sources") or [],
            "context": rag.get("context"),
        },
        "medication_checks": agent_result.get("medication_checks") or {},
        "notes": agent_result.get("notes") or [],
    }


def _compact_research_agent(agent_result):
    if not isinstance(agent_result, dict):
        return {}
    return {
        "engine": agent_result.get("engine"),
        "model": agent_result.get("model"),
        "pubmed_query": agent_result.get("pubmed_query"),
        "pubmed_error": agent_result.get("pubmed_error"),
        "pubmed_papers": agent_result.get("pubmed_papers") or [],
        "report": agent_result.get("report") or {},
        "error": agent_result.get("error"),
    }


def _compact_evidence_reviewer(agent_result):
    if not isinstance(agent_result, dict):
        return {}
    return {
        "engine": agent_result.get("engine"),
        "model": agent_result.get("model"),
        "report": agent_result.get("report") or {},
        "error": agent_result.get("error"),
    }


def _compact_report_agent(agent_result):
    if not isinstance(agent_result, dict):
        return {}
    return {
        "engine": agent_result.get("engine"),
        "model": agent_result.get("model"),
        "error": agent_result.get("error"),
        "report": agent_result.get("report") or {},
        "report_packet": agent_result.get("report_packet") or {},
    }


def _build_saved_evidence_catalog():
    return [
        {
            "source_key": "lifestyle_assessment",
            "display_name": SOURCE_DISPLAY_NAMES["lifestyle_assessment"],
            "description": "Saved lifestyle-triage output generated before the main pipeline.",
        },
        {
            "source_key": "clinical_review",
            "display_name": SOURCE_DISPLAY_NAMES["clinical_review"],
            "description": "Saved clinical review, medication safety findings, and guideline evidence.",
        },
        {
            "source_key": "research_review",
            "display_name": SOURCE_DISPLAY_NAMES["research_review"],
            "description": "Saved literature synthesis and PubMed evidence captured in the submission workflow.",
        },
        {
            "source_key": "evidence_quality_review",
            "display_name": SOURCE_DISPLAY_NAMES["evidence_quality_review"],
            "description": "Saved evidence-quality assessment of the clinical and research outputs.",
        },
        {
            "source_key": "final_clinical_report",
            "display_name": SOURCE_DISPLAY_NAMES["final_clinical_report"],
            "description": "Saved final clinician-facing report for the submission.",
        },
        {
            "source_key": "generated_report_packet",
            "display_name": SOURCE_DISPLAY_NAMES["generated_report_packet"],
            "description": "Saved packet that the final report agent used to build the report.",
        },
        {
            "source_key": "medication_image_ocr",
            "display_name": SOURCE_DISPLAY_NAMES["medication_image_ocr"],
            "description": "Saved OCR or Gemini vision extraction from uploaded medication images.",
        },
        {
            "source_key": "uploaded_document_review",
            "display_name": SOURCE_DISPLAY_NAMES["uploaded_document_review"],
            "description": "Saved metadata and summaries for uploaded medication and investigation files.",
        },
        {
            "source_key": "doctor_report_notes",
            "display_name": SOURCE_DISPLAY_NAMES["doctor_report_notes"],
            "description": "Doctor-authored notes saved into this report after generation.",
        },
        {
            "source_key": "question_guidelines",
            "display_name": SOURCE_DISPLAY_NAMES["question_guidelines"],
            "description": "Guideline passages retrieved from the local guideline library for the doctor's current question.",
        },
    ]


def _build_saved_evidence(submission):
    form_data = submission.get("form_data") or {}
    pipeline = form_data.get("clinical_pipeline") or {}

    uploaded_files = _maybe_json_value(form_data.get("uploadedFiles")) or []
    uploaded_drug_analysis = _maybe_json_value(form_data.get("uploadedDrugAnalysis")) or {}
    uploaded_file_summary = _maybe_json_value(form_data.get("uploadedFileSummary")) or {}
    doctor_notes = form_data.get("doctor_report_notes") or []
    if not isinstance(doctor_notes, list):
        doctor_notes = []

    return {
        "workflow_status": {
            "status": pipeline.get("status"),
            "stopped_after": pipeline.get("stopped_after"),
            "error": pipeline.get("error"),
            "workflow": pipeline.get("workflow") or [],
        },
        "sequential_agent_outputs": {
            "lifestyle_assessment": _compact_lifestyle_agent(pipeline.get("lifestyle_agent")),
            "clinical_review": _compact_clinical_agent(pipeline.get("clinical_agent")),
            "research_review": _compact_research_agent(pipeline.get("research_agent")),
            "evidence_quality_review": _compact_evidence_reviewer(pipeline.get("evidence_reviewer_agent")),
            "final_clinical_report": _compact_report_agent(pipeline.get("report_agent")),
        },
        "saved_submission_artifacts": {
            "medication_image_ocr": uploaded_drug_analysis,
            "uploaded_document_review": {
                "uploaded_files": _compact_uploaded_files(uploaded_files),
                "uploaded_file_summary": uploaded_file_summary,
            },
            "doctor_report_notes": doctor_notes[-25:],
        },
    }


def _trim_saved_evidence(saved_evidence):
    """Drop the largest nested saved artifacts first when the prompt grows too large."""
    sequential = saved_evidence.get("sequential_agent_outputs") or {}
    final_report = sequential.get("final_clinical_report") or {}
    report_packet = final_report.get("report_packet")
    if report_packet and _json_size(saved_evidence) > MAX_CONTEXT_JSON_CHARS:
        final_report["report_packet"] = {
            "notice": (
                "The saved generated report packet was omitted because the chat context grew too large. "
                "Use the saved final report and other saved sequential-agent outputs."
            )
        }

    clinical_review = sequential.get("clinical_review") or {}
    rag = clinical_review.get("rag") or {}
    if rag.get("context") and _json_size(saved_evidence) > MAX_CONTEXT_JSON_CHARS:
        rag["context"] = (
            "The saved guideline context text was omitted because the chat context grew too large. "
            "Use the saved source list and saved clinical review findings."
        )

    research_review = sequential.get("research_review") or {}
    if research_review.get("pubmed_papers") and _json_size(saved_evidence) > MAX_CONTEXT_JSON_CHARS:
        research_review["pubmed_papers"] = [{
            "notice": (
                "The saved PubMed paper list was omitted because the chat context grew too large. "
                "Use the saved research summary and cited evidence already stored in the submission."
            )
        }]


def _normalize_reference_item(item):
    if isinstance(item, dict):
        source_key = str(
            item.get("source_key")
            or item.get("source_agent")
            or item.get("source_type")
            or ""
        ).strip()
        evidence_source = item.get("evidence_source") or SOURCE_DISPLAY_NAMES.get(
            source_key,
            SOURCE_DISPLAY_NAMES["saved_clinical_record"],
        )
        record_location = (
            item.get("record_location")
            or item.get("label")
            or item.get("section")
            or "Saved clinical record"
        )
        supporting_evidence = (
            item.get("supporting_evidence")
            or item.get("support")
            or item.get("text")
            or item.get("detail")
            or ""
        )
        return {
            "evidence_source": compact_text(evidence_source, max_chars=120),
            "record_location": compact_text(record_location, max_chars=220),
            "supporting_evidence": compact_text(supporting_evidence, max_chars=600),
        }
    if item:
        return {
            "evidence_source": SOURCE_DISPLAY_NAMES["saved_clinical_record"],
            "record_location": "Saved clinical record",
            "supporting_evidence": compact_text(item, max_chars=600),
        }
    return None


def _normalize_answer(raw_answer):
    answer = raw_answer if isinstance(raw_answer, dict) else {}
    references = answer.get("references") if isinstance(answer.get("references"), list) else []
    normalized_references = []

    for item in references[:12]:
        normalized = _normalize_reference_item(item)
        if normalized:
            normalized_references.append(normalized)

    limitations = answer.get("limitations") if isinstance(answer.get("limitations"), list) else []
    return {
        "direct_answer": compact_text(answer.get("direct_answer"), max_chars=2500),
        "reasoning_summary": compact_text(answer.get("reasoning_summary"), max_chars=2500),
        "references": normalized_references,
        "uncertainty": compact_text(answer.get("uncertainty"), max_chars=1500),
        "limitations": [compact_text(item, max_chars=700) for item in limitations[:8] if str(item or "").strip()],
    }


def load_report_chat_submission(submission_id, *, get_db_connection, safe_json_loads):
    """Load exactly one submission row and parse its saved form data."""
    normalized_id = normalize_submission_id(submission_id)
    conn = get_db_connection()
    try:
        row = conn.execute(
            """
            SELECT id, full_name, age, mobile, email, form_data
            FROM intake_forms
            WHERE id = ?
            """,
            (normalized_id,),
        ).fetchone()
    finally:
        conn.close()

    if not row:
        raise ReportChatNotFound(f"Submission INT-{normalized_id} was not found.")

    return {
        "id": int(row["id"]),
        "code_no": f"INT-{row['id']}",
        "form_data": safe_json_loads(row["form_data"], {}),
    }


def _build_guideline_context(question, retrieve_guideline_context=None):
    if not callable(retrieve_guideline_context):
        return {
            "query": question,
            "context": "",
            "sources": [],
            "retrieval_status": "unavailable",
            "retrieval_error": "Guideline retrieval is not configured.",
        }
    try:
        context = retrieve_guideline_context(question, top_k=6)
    except Exception as exc:
        return {
            "query": question,
            "context": "",
            "sources": [],
            "retrieval_status": "error",
            "retrieval_error": compact_text(str(exc), max_chars=700),
        }
    if not isinstance(context, dict):
        return {
            "query": question,
            "context": compact_text(context, max_chars=MAX_CONTEXT_STRING_CHARS),
            "sources": [],
            "retrieval_status": "ok",
        }
    return {
        "query": context.get("query") or question,
        "context": compact_text(context.get("context"), max_chars=MAX_CONTEXT_STRING_CHARS),
        "sources": context.get("sources") or [],
        "retrieval_status": "ok",
    }


def build_report_chat_packet(submission, question, retrieve_guideline_context=None):
    """Build the chat packet from saved multi-agent evidence for one completed submission."""
    clean_question = _clean_question(question)
    form_data = submission.get("form_data") or {}
    pipeline = form_data.get("clinical_pipeline") or {}
    status = str(pipeline.get("status") or "").strip().lower()
    if status != "completed":
        raise ReportChatUnavailable("Report generation is not completed for this submission.")

    report_agent = pipeline.get("report_agent")
    if not isinstance(report_agent, dict):
        raise ReportChatUnavailable("No report-agent output is saved for this submission.")

    report = report_agent.get("report")
    if not isinstance(report, dict) or not report:
        raise ReportChatUnavailable("The report-agent output does not contain a generated report.")

    saved_evidence = _compact_for_prompt(_build_saved_evidence(submission))
    _trim_saved_evidence(saved_evidence)
    guideline_context = _compact_for_prompt(
        _build_guideline_context(clean_question, retrieve_guideline_context)
    )
    packet = {
        "submission_id": int(submission["id"]),
        "code_no": submission["code_no"],
        "doctor_question": clean_question,
        "strict_context_boundary": (
            "Use only this selected submission's saved evidence, doctor report notes, and the "
            "question-specific guideline passages retrieved into this packet. Do not retrieve other "
            "patients, other submissions, PubMed, medication labels, websites, or outside evidence."
        ),
        "saved_evidence_catalog": _build_saved_evidence_catalog(),
        "saved_evidence": saved_evidence,
        "question_guideline_context": guideline_context,
    }

    if _json_size(packet) > MAX_CONTEXT_JSON_CHARS:
        raise ReportChatUnavailable(
            "The saved report-chat context for this submission is too large to process safely."
        )

    packet["context_hash"] = _context_hash({
        "saved_evidence": saved_evidence,
        "question_guideline_context": guideline_context,
    })
    return packet


def _report_chat_agent_specs():
    specs = []
    for name in REPORT_CHAT_AGENT_NAMES:
        definition = get_agent_definition(name)
        specs.append({
            "name": name,
            "role": definition["role"],
            "goal": definition["goal"],
            "backstory": definition["backstory"],
            "allow_delegation": name == "report_chat",
            "verbose": True,
        })
    return specs


def call_report_chat_agent(packet, *, api_key, model_name=GEMINI_REPORT_CHAT_MODEL, timeout=60):
    """Run the CrewAI report chat agent over one saved multi-agent submission packet."""
    task_def = get_task_definition("report_chat")
    return run_crewai_json_hierarchical_crew(
        agent_specs=_report_chat_agent_specs(),
        task_prompt=(
            f"{task_def['description']}\n\n"
            f"{json.dumps(packet, ensure_ascii=False, indent=2)}"
        ),
        expected_output=task_def["expected_output"],
        api_key=api_key,
        manager_model_name=model_name,
        default_model_name=model_name,
        task_agent_name="report_chat",
        max_tokens=4096,
        timeout=timeout,
        label="CrewAI report chat agent",
    )


def build_fallback_report_chat_answer(packet, error=None):
    """Return an auditable response when the CrewAI runtime is unavailable."""
    limitation = "The CrewAI report chat agent could not complete this request."
    if error:
        limitation = f"{limitation} Runtime detail: {compact_text(error, max_chars=500)}"
    return {
        "direct_answer": (
            "I cannot answer this report question right now because the report chat agent did not complete. "
            "No cross-patient data or fresh retrieval was used."
        ),
        "reasoning_summary": (
            "The request was limited to the saved sequential-agent outputs and saved upload evidence for this "
            "submission, but the hierarchical chat step failed before it could analyze that context."
        ),
        "references": [{
            "evidence_source": SOURCE_DISPLAY_NAMES["saved_clinical_record"],
            "record_location": f"{packet.get('code_no', 'Selected submission')} saved evidence bundle",
            "supporting_evidence": (
                "The response is limited to the selected submission's saved sequential-agent outputs and saved "
                "upload evidence."
            ),
        }],
        "uncertainty": "The question cannot be answered until the report chat agent runs successfully.",
        "limitations": [limitation],
    }


def run_report_chat_agent(submission_id, question, dependencies, *, model_name=GEMINI_REPORT_CHAT_MODEL):
    """Load one completed report and answer the doctor's question about it."""
    clean_question = _clean_question(question)
    submission = load_report_chat_submission(
        submission_id,
        get_db_connection=dependencies["get_db_connection"],
        safe_json_loads=dependencies["safe_json_loads"],
    )
    packet = build_report_chat_packet(
        submission,
        clean_question,
        retrieve_guideline_context=dependencies.get("retrieve_guideline_context"),
    )

    try:
        answer = call_report_chat_agent(
            packet,
            api_key=dependencies.get("gemini_api_key"),
            model_name=model_name,
        )
        llm_error = None
    except RuntimeError as exc:
        answer = build_fallback_report_chat_answer(packet, error=str(exc))
        llm_error = str(exc)

    normalized_answer = _normalize_answer(answer)
    if not normalized_answer["direct_answer"]:
        normalized_answer["direct_answer"] = (
            "The saved clinical record does not contain enough information to answer that question."
        )
    if not normalized_answer["limitations"] and llm_error:
        normalized_answer["limitations"] = [compact_text(llm_error, max_chars=700)]

    return {
        "submission_id": int(submission["id"]),
        "code_no": submission["code_no"],
        "question": clean_question,
        "answer": normalized_answer,
        "model": model_name,
        "context_hash": packet["context_hash"],
        "engine": "crewai",
        "error": llm_error,
    }
