"""Report packet assembly and fallback logic for the final report agent."""

import json

from tools.crewai_agent_tools import run_crewai_json_agent


GEMINI_REPORT_MODEL = "gemini-2.5-flash"

REPORT_SYSTEM_PROMPT = """
You are a final report agent.

You receive the complete pipeline output from multiple CrewAI agents and deterministic tools.
Your task is to produce one structured, clinician-facing final report.

Return ONLY a valid JSON object. No markdown and no text outside JSON.

Response format:
{
  "report_title": "short title",
  "report_type": "lifestyle_triage or full_clinical_evidence_review",
  "patient_snapshot": {
    "submission_id": "id if supplied",
    "age": "age if supplied",
    "sex": "sex or gender if supplied",
    "presenting_question": "short question or complaint"
  },
  "clinical_summary": "short clinician-facing clinical summary",
  "executive_summary": "short summary of the whole case",
  "findings": ["important final report findings"],
  "urgent_safety_alerts": ["urgent medication, clinical, or uncertainty alerts"],
  "clinical_findings": ["key clinical findings from the pipeline"],
  "medication_safety": ["medication safety findings"],
  "evidence_summary": ["evidence quality and source-supported points"],
  "clinician_actions": ["specific items for clinician review"],
  "missing_information": ["missing data needed before decisions"],
  "citations": ["citations supplied by earlier agents only"],
  "source_citations": ["citations supplied by earlier agents only"],
  "confidence": "high or moderate or low",
  "limitations": ["limits of the report"],
  "structured_sections": [
    {
      "heading": "section heading",
      "items": ["plain text item"]
    }
  ]
}

Rules:
- Do not diagnose.
- Do not prescribe.
- Do not invent facts, citations, PMIDs, medication facts, guideline statements, or lab values.
- Base the report only on the supplied pipeline output.
- Preserve urgent safety alerts prominently.
- Include citation quality concerns when the evidence reviewer flagged them.
- Keep the output structured and concise enough for a PDF report.
- Do not use Markdown, bold markers, bullets, headings, or asterisks inside string values. Use plain text only.
""".strip()

ARABIC_PDF_SYSTEM_PROMPT = """
You are an Arabic medical report translator.

You receive a structured clinical report JSON. Translate the report content into clear Modern Standard Arabic for the PDF only.

Return ONLY a valid JSON object. No markdown and no text outside JSON.

Response format:
{
  "report_title": "Arabic report title",
  "patient_snapshot": {
    "submission_id": "id if supplied",
    "age": "age if supplied",
    "sex": "sex or gender if supplied"
  },
  "clinical_summary": "Arabic clinical summary",
  "findings": ["Arabic finding"],
  "urgent_safety_alerts": ["Arabic urgent alert"],
  "medication_safety": ["Arabic medication safety point"],
  "evidence_summary": ["Arabic evidence summary point"],
  "clinician_actions": ["Arabic clinician action"],
  "missing_information": ["Arabic missing information item"],
  "citations": ["Keep citations, file names, page numbers, PMIDs, medication names, units, and lab values readable"],
  "limitations": ["Arabic limitation"]
}

Rules:
- Translate only the report prose into Arabic.
- Keep medication names, lab values, units, file names, page numbers, guideline names, and PMIDs unchanged when needed.
- Do not add new facts, citations, PMIDs, medication facts, guideline statements, diagnoses, or prescriptions.
- Base the Arabic report only on the supplied structured report.
- Use concise clinician-facing Arabic.
- Do not use Markdown, bullets, asterisks, or headings inside string values. Use plain text only.
""".strip()


def _as_list(value):
    """Normalize report fields into lists of strings."""
    if isinstance(value, list):
        return [str(item) for item in value if item not in (None, "")]
    if value in (None, ""):
        return []
    return [str(value)]


def _collect_citations(*reports):
    """Collect unique citations from earlier structured reports."""
    citations = []
    seen = set()
    for report in reports:
        for citation in _as_list((report or {}).get("citations") or (report or {}).get("source_citations")):
            key = citation.lower()
            if key in seen:
                continue
            seen.add(key)
            citations.append(citation)
    return citations


def _compact_json(value, max_chars=9000):
    """Return compact JSON text for report-agent context."""
    try:
        text = json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError):
        text = str(value or "")
    from core.agent_utils import compact_text
    return compact_text(text, max_chars)


def _compact_pubmed_papers(papers, limit=3):
    """Keep only the most useful PubMed fields for the final report agent."""
    from core.agent_utils import compact_text
    compacted = []
    for paper in (papers or [])[:limit]:
        compacted.append({
            "pmid": paper.get("pmid"),
            "title": paper.get("title"),
            "journal": paper.get("journal"),
            "year": paper.get("year"),
            "citation": paper.get("citation"),
            "abstract": compact_text(paper.get("abstract"), 700),
        })
    return compacted


def _compact_medication_checks(medication_checks):
    """Reduce medication-check payload size while preserving clinician-useful details."""
    from core.agent_utils import compact_text
    medication_checks = medication_checks or {}
    openfda_rows = []
    for item in (medication_checks.get("openfda") or [])[:3]:
        label = item.get("label") or {}
        openfda_rows.append({
            "query": item.get("query"),
            "found": item.get("found"),
            "message": item.get("message") or item.get("error"),
            "contraindications": compact_text(label.get("contraindications"), 500),
            "drug_interactions": compact_text(label.get("drug_interactions"), 500),
            "warnings": compact_text(label.get("warnings"), 500),
        })

    return {
        "drug_candidates": (medication_checks.get("drug_candidates") or [])[:6],
        "label_flags": (medication_checks.get("label_flags") or [])[:6],
        "openfda": openfda_rows,
    }


def build_report_packet(pipeline_result):
    """Extract the pipeline fields that the final report agent needs."""
    pipeline_result = pipeline_result or {}
    lifestyle = pipeline_result.get("lifestyle_agent") or {}
    clinical = pipeline_result.get("clinical_agent") or {}
    research = pipeline_result.get("research_agent") or {}
    evidence = pipeline_result.get("evidence_reviewer_agent") or {}

    return {
        "submission_id": pipeline_result.get("submission_id"),
        "status": pipeline_result.get("status"),
        "stopped_after": pipeline_result.get("stopped_after"),
        "lifestyle_agent": lifestyle,
        "clinical_agent": {
            "input": clinical.get("input", {}),
            "clinical_report": (clinical.get("clinical_agent") or {}).get("report", {}),
            "medication_checks": _compact_medication_checks(clinical.get("medication_checks", {})),
            "rag_sources": (clinical.get("rag") or {}).get("sources", []),
            "notes": clinical.get("notes", []),
        },
        "research_agent": {
            "pubmed_query": research.get("pubmed_query"),
            "pubmed_error": research.get("pubmed_error"),
            "pubmed_papers": _compact_pubmed_papers(research.get("pubmed_papers", [])),
            "report": research.get("report", {}),
        },
        "evidence_reviewer_agent": {
            "report": evidence.get("report", {}),
            "error": evidence.get("error"),
        },
        "existing_final_report": pipeline_result.get("final_report"),
    }


def call_report_agent(report_packet, *, api_key, model_name=GEMINI_REPORT_MODEL, timeout=60):
    """Run the CrewAI final report agent and parse the structured JSON report."""
    return run_crewai_json_agent(
        role="Final Structured Report Agent",
        goal="Create a structured final report from the completed pipeline output.",
        backstory=REPORT_SYSTEM_PROMPT,
        task_prompt=(
            "Create the final structured JSON report from this pipeline output.\n\n"
            f"{json.dumps(report_packet, ensure_ascii=False, indent=2)}"
        ),
        expected_output="A valid JSON object matching the requested final report response format.",
        api_key=api_key,
        model_name=model_name,
        max_tokens=8192,
        timeout=timeout,
        label="CrewAI report agent",
    )


def build_fallback_report(pipeline_result, error=None):
    """Build a structured report when the CrewAI report agent is unavailable."""
    pipeline_result = pipeline_result or {}
    lifestyle = pipeline_result.get("lifestyle_agent") or {}
    clinical_outer = pipeline_result.get("clinical_agent") or {}
    clinical_report = (clinical_outer.get("clinical_agent") or {}).get("report", {})
    research_report = (pipeline_result.get("research_agent") or {}).get("report", {})
    evidence_report = (pipeline_result.get("evidence_reviewer_agent") or {}).get("report", {})
    inputs = clinical_outer.get("input", {})

    safety_alerts = []
    safety_alerts.extend(_as_list(lifestyle.get("flags")))
    safety_alerts.extend(_as_list(clinical_report.get("red_flags")))
    safety_alerts.extend(_as_list(evidence_report.get("clinician_review_priorities"))[:3])

    report_type = "full_clinical_evidence_review" if clinical_report or research_report else "lifestyle_triage"
    limitations = []
    limitations.extend(_as_list(clinical_report.get("limitations")))
    limitations.extend(_as_list(research_report.get("limitations")))
    limitations.extend(_as_list(evidence_report.get("limitations")))
    if error:
        limitations.append(f"Report agent unavailable: {error}")

    return {
        "report_title": "AI Clinical Evidence Report",
        "report_type": report_type,
        "patient_snapshot": {
            "submission_id": str(pipeline_result.get("submission_id") or inputs.get("submission_id") or ""),
            "age": str(inputs.get("age") or ""),
            "sex": str(inputs.get("sex") or inputs.get("gender") or ""),
            "presenting_question": inputs.get("query") or lifestyle.get("reasoning") or "",
        },
        "executive_summary": (
            clinical_report.get("clinical_summary")
            or research_report.get("research_summary")
            or lifestyle.get("reasoning")
            or "Structured report generated from available pipeline output."
        ),
        "clinical_summary": clinical_report.get("clinical_summary") or lifestyle.get("reasoning") or "",
        "findings": _as_list(clinical_report.get("key_findings")) or _as_list(research_report.get("evidence_points")),
        "urgent_safety_alerts": safety_alerts,
        "clinical_findings": _as_list(clinical_report.get("key_findings")),
        "medication_safety": _as_list(clinical_report.get("medication_safety")),
        "evidence_summary": _as_list(research_report.get("evidence_points")),
        "clinician_actions": _as_list(research_report.get("suggested_clinician_review")) or _as_list(evidence_report.get("clinician_review_priorities")),
        "missing_information": _as_list(clinical_report.get("missing_information")) or _as_list(evidence_report.get("missing_evidence")),
        "citations": _collect_citations(clinical_report, research_report),
        "source_citations": _collect_citations(clinical_report, research_report),
        "confidence": evidence_report.get("overall_evidence_quality") or research_report.get("confidence") or clinical_report.get("confidence") or lifestyle.get("confidence") or "low",
        "limitations": limitations,
        "structured_sections": [
            {"heading": "Urgent Safety Alerts", "items": safety_alerts},
            {"heading": "Clinical Findings", "items": _as_list(clinical_report.get("key_findings"))},
            {"heading": "Evidence Summary", "items": _as_list(research_report.get("evidence_points"))},
            {"heading": "Clinician Actions", "items": _as_list(research_report.get("suggested_clinician_review"))},
            {"heading": "Missing Information", "items": _as_list(clinical_report.get("missing_information"))},
        ],
    }


def call_arabic_pdf_report(report, *, api_key, model_name=GEMINI_REPORT_MODEL, timeout=60):
    """Run the CrewAI Arabic PDF translator and parse the structured Arabic report."""
    return run_crewai_json_agent(
        role="Arabic PDF Report Translator",
        goal="Translate the final structured clinical report into Arabic for PDF generation only.",
        backstory=ARABIC_PDF_SYSTEM_PROMPT,
        task_prompt=(
            "Translate this structured report into the requested Arabic JSON shape for the PDF only.\n\n"
            f"{json.dumps(report or {}, ensure_ascii=False, indent=2)}"
        ),
        expected_output="A valid JSON object matching the requested Arabic PDF report response format.",
        api_key=api_key,
        model_name=model_name,
        max_tokens=8192,
        timeout=timeout,
        label="CrewAI Arabic PDF translator",
    )


def build_fallback_arabic_pdf_report(report, error=None):
    """Build an Arabic-labeled PDF report if translation is unavailable."""
    report = report or {}
    limitations = []
    if error:
        limitations.append(f"طھط¹ط°ط± طھظˆظ„ظٹط¯ ط§ظ„طھط±ط¬ظ…ط© ط§ظ„ط¹ط±ط¨ظٹط© ط¢ظ„ظٹط§ظ‹: {error}")
    return {
        "report_title": "طھظ‚ط±ظٹط± ط§ظ„ظ…ط±ط§ط¬ط¹ط© ط§ظ„ط³ط±ظٹط±ظٹط©",
        "patient_snapshot": report.get("patient_snapshot") or {},
        "clinical_summary": "طھط¹ط°ط±طھ طھط±ط¬ظ…ط© ط§ظ„طھظ‚ط±ظٹط± ط§ظ„ط³ط±ظٹط±ظٹ ط¥ظ„ظ‰ ط§ظ„ط¹ط±ط¨ظٹط©. ظٹط±ط¬ظ‰ ظ…ط±ط§ط¬ط¹ط© ط§ظ„طھظ‚ط±ظٹط± ط§ظ„ظ…ظ†ط¸ظ… ظپظٹ طµظپط­ط© ط§ظ„ظ†ط¸ط§ظ… ط£ظˆ ط¥ط¹ط§ط¯ط© طھظˆظ„ظٹط¯ ط§ظ„طھظ‚ط±ظٹط± ط¨ط¹ط¯ طھظˆظپط± ط®ط¯ظ…ط© ط§ظ„طھط±ط¬ظ…ط©.",
        "findings": [],
        "urgent_safety_alerts": [],
        "medication_safety": [],
        "evidence_summary": [],
        "clinician_actions": [],
        "missing_information": [],
        "citations": _as_list(report.get("citations") or report.get("source_citations")),
        "limitations": limitations,
    }


def _contains_arabic(value):
    """Return True when a nested report value contains Arabic characters."""
    import re
    if isinstance(value, dict):
        return any(_contains_arabic(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_arabic(item) for item in value)
    return bool(re.search(r"[\u0600-\u06FF]", str(value or "")))


def build_arabic_pdf_report(report, *, api_key, model_name=GEMINI_REPORT_MODEL):
    """Return an Arabic report object for PDF generation only."""
    try:
        arabic_report = call_arabic_pdf_report(report, api_key=api_key, model_name=model_name)
        if not _contains_arabic(arabic_report):
            raise RuntimeError("Arabic translator did not return Arabic content.")
        return arabic_report, None
    except RuntimeError as exc:
        return build_fallback_arabic_pdf_report(report, error=str(exc)), str(exc)