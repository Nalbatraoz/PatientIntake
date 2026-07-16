"""Consolidated public entry points for the CrewAI agents.

The original agent modules were moved under ``nodes`` as private helpers so their
packet-building and fallback behavior stays intact. Import from this module in
application code.
"""

from nodes._clinical_agent import (
    build_agent_inputs,
    build_clinical_agent_response,
    build_clinical_evidence_context,
    build_evidence_packet,
    call_gemini_clinical_agent,
)
from nodes._evidence_reviewer_agent import (
    build_evidence_review_packet,
    call_gemini_evidence_reviewer,
    run_evidence_reviewer_agent,
)
from nodes._lifestyle_agent import run_lifestyle_agent
from nodes._report_agent import (
    ARABIC_PDF_SYSTEM_PROMPT,
    GEMINI_REPORT_MODEL,
    REPORT_SYSTEM_PROMPT,
    build_arabic_pdf_report,
    build_fallback_arabic_pdf_report,
    build_fallback_report,
    build_report_packet,
    call_report_agent,
    save_report_pdf,
    run_report_agent,
    call_arabic_pdf_report,
)
from nodes._report_chat_agent import (
    ReportChatError,
    ReportChatNotFound,
    ReportChatUnavailable,
    build_report_chat_packet,
    call_report_chat_agent,
    load_report_chat_submission,
    normalize_submission_id,
    run_report_chat_agent,
)
from nodes._report_patch_agent import (
    GEMINI_REPORT_PATCH_MODEL,
    build_report_patch_packet,
    call_report_patch_agent,
    run_report_patch_agent,
)
from nodes._research_agent import (
    build_research_context,
    build_pubmed_query,
    call_gemini_research_agent,
    fetch_pubmed_papers,
    run_research_agent,
)


AGENT_NAMES = {
    "clinical": "Clinical Evidence Review Agent",
    "evidence_reviewer": "Evidence Quality Reviewer Agent",
    "lifestyle": "Lifestyle Triage Agent",
    "research": "Research Synthesis Agent",
    "report": "Final Structured Report Agent",
    "report_chat": "Report Explanation Chat Agent",
    "report_patch": "Final Report Patch Agent",
    "arabic_pdf": "Arabic PDF Report Translator",
}
