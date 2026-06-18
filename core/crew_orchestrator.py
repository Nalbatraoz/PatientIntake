"""CrewAI Flow orchestration for the clinical pipeline."""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any, Callable
from uuid import uuid4

from crewai.flow.flow import Flow, listen, router, start
from crewai.flow.persistence import SQLiteFlowPersistence, persist
from pydantic import BaseModel, Field, PrivateAttr

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FLOW_DB_PATH = (
    os.environ.get("CREWAI_FLOW_DB_PATH")
    or os.environ.get("DB_PATH")
    or os.path.join(BASE_DIR, "flow_states.db")
)


def default_clinical_query(data):
    """Build the default clinical query when the caller did not provide one."""
    parts = [
        data.get("chiefComplaint") or data.get("chief_complaint"),
        data.get("medicalHistory") or data.get("medical_history"),
        data.get("currentMedications") or data.get("current_medications"),
        data.get("investigationResults") or data.get("investigation_results"),
    ]
    context = " ".join(str(part) for part in parts if part).strip()
    if context:
        return f"Clinical review for men's sexual health symptoms: {context}"
    return "Clinical review for men's sexual health symptoms, medication safety, and guideline context."


@dataclass
class ClinicalFlowRuntime:
    """Runtime-only dependencies used by the CrewAI Flow steps."""

    gemini_api_key: str
    gemini_research_model: str
    gemini_evidence_reviewer_model: str
    gemini_report_model: str
    clinical_agent_module: Any
    clinical_agent_dependencies: Callable[[], dict[str, Any]]
    run_lifestyle_agent: Callable[..., dict[str, Any]]
    run_research_agent: Callable[..., dict[str, Any]]
    run_evidence_reviewer_agent: Callable[..., dict[str, Any]]
    run_report_agent: Callable[..., dict[str, Any]]
    build_arabic_pdf_report: Callable[..., Any]
    save_report_pdf: Callable[..., dict[str, Any]]
    upload_dir: str
    storage_backend: str
    storage_is_ephemeral: bool


class ClinicalFlowState(BaseModel):
    """Structured Pydantic state persisted by CrewAI Flow."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    workflow: list[str] = Field(
        default_factory=lambda: [
            "lifestyle_agent",
            "medication_check_and_crewai_rag",
            "clinical_agent",
            "research_agent",
            "evidence_reviewer_agent",
            "report_agent",
        ]
    )
    submission_id: Any = None
    input_data: dict[str, Any] = Field(default_factory=dict)
    clinical_input: dict[str, Any] = Field(default_factory=dict)
    status: str = "started"
    error: str = ""
    stopped_after: str = ""
    lifestyle_agent: dict[str, Any] = Field(default_factory=dict)
    clinical_agent: dict[str, Any] = Field(default_factory=dict)
    research_agent: dict[str, Any] = Field(default_factory=dict)
    evidence_reviewer_agent: dict[str, Any] = Field(default_factory=dict)
    report_agent: dict[str, Any] = Field(default_factory=dict)
    final_report: dict[str, Any] = Field(default_factory=dict)
    report_pdf: dict[str, Any] = Field(default_factory=dict)
    report_pdf_translation_error: str = ""

    def to_pipeline_result(self) -> dict[str, Any]:
        """Return the legacy pipeline payload expected by the rest of the app."""
        result = {
            "workflow": list(self.workflow),
            "submission_id": self.submission_id,
            "status": self.status,
        }

        if self.error:
            result["error"] = self.error
        if self.lifestyle_agent:
            result["lifestyle_agent"] = self.lifestyle_agent
        if self.clinical_agent:
            result["clinical_agent"] = self.clinical_agent
        if self.research_agent:
            result["research_agent"] = self.research_agent
        if self.evidence_reviewer_agent:
            result["evidence_reviewer_agent"] = self.evidence_reviewer_agent
        if self.report_agent:
            result["report_agent"] = self.report_agent
        if self.final_report:
            result["final_report"] = self.final_report
        if self.report_pdf_translation_error:
            result["report_pdf_translation_error"] = self.report_pdf_translation_error
        if self.report_pdf:
            result["report_pdf"] = self.report_pdf
        if self.stopped_after:
            result["stopped_after"] = self.stopped_after
        return result


@persist(SQLiteFlowPersistence(FLOW_DB_PATH))
class ClinicalPipelineFlow(Flow[ClinicalFlowState]):
    """CrewAI Flow version of the clinical pipeline with structured state."""

    _runtime: ClinicalFlowRuntime | None = PrivateAttr(default=None)

    def __init__(self, *, runtime: ClinicalFlowRuntime | None = None, **kwargs):
        super().__init__(**kwargs)
        self._runtime = runtime

    def _require_runtime(self) -> ClinicalFlowRuntime:
        """Return the non-persisted execution context for active Flow steps."""
        if self._runtime is None:
            raise RuntimeError("Clinical Flow runtime is not attached.")
        return self._runtime

    @start()
    def run_lifestyle(self):
        """Run lifestyle triage first so it can short-circuit the pipeline."""
        runtime = self._require_runtime()
        if not runtime.gemini_api_key:
            self.state.status = "error"
            self.state.error = "GEMINI_API_KEY is not configured."
            return {"error": self.state.error}

        lifestyle_result = runtime.run_lifestyle_agent(
            self.state.input_data,
            runtime.gemini_api_key,
        )
        self.state.lifestyle_agent = lifestyle_result
        return lifestyle_result

    @router(run_lifestyle)
    def route_after_lifestyle(self):
        """Preserve the original lifestyle triage branching logic."""
        if self.state.status == "error":
            return "run_report"

        if not self.state.lifestyle_agent.get("proceed_to_pipeline"):
            self.state.status = "completed"
            self.state.stopped_after = "lifestyle_agent"
            self.state.final_report = {
                "type": "lifestyle_triage",
                "summary": self.state.lifestyle_agent.get("reasoning", ""),
                "recommendations": self.state.lifestyle_agent.get("lifestyle_recommendations", []),
                "flags": self.state.lifestyle_agent.get("flags", []),
            }
            return "stop_after_lifestyle"

        return "continue_pipeline"

    @listen("continue_pipeline")
    def run_clinical(self):
        """Run the clinical agent with the same inputs as the legacy orchestrator."""
        runtime = self._require_runtime()
        clinical_input = dict(self.state.input_data)
        clinical_input.setdefault("query", default_clinical_query(self.state.input_data))
        if self.state.submission_id is not None:
            clinical_input["submission_id"] = self.state.submission_id

        clinical_result = runtime.clinical_agent_module.build_clinical_agent_response(
            clinical_input,
            runtime.clinical_agent_dependencies(),
        )
        self.state.clinical_input = clinical_input
        self.state.clinical_agent = clinical_result
        return clinical_result

    @listen(run_clinical)
    def run_research(self):
        """Run research synthesis on the clinical packet."""
        runtime = self._require_runtime()
        research_result = runtime.run_research_agent(
            self.state.clinical_agent,
            api_key=runtime.gemini_api_key,
            model_name=runtime.gemini_research_model,
            max_pubmed_results=3,
        )
        self.state.research_agent = research_result
        return research_result

    @router(run_research)
    def run_evidence_review(self):
        """Run the evidence reviewer on the research result."""
        runtime = self._require_runtime()
        evidence_review_result = runtime.run_evidence_reviewer_agent(
            self.state.research_agent,
            api_key=runtime.gemini_api_key,
            model_name=runtime.gemini_evidence_reviewer_model,
        )
        self.state.evidence_reviewer_agent = evidence_review_result
        self.state.status = "completed"
        self.state.stopped_after = "evidence_reviewer_agent"
        self.state.final_report = {
            "research": self.state.research_agent.get("report"),
            "evidence_review": evidence_review_result.get("report"),
        }
        return "run_report"

    @listen("run_report")
    def finalize_report(self):
        """Run the final report agent and save the resulting PDF."""
        runtime = self._require_runtime()
        report_result = runtime.run_report_agent(
            self.state.to_pipeline_result(),
            api_key=runtime.gemini_api_key,
            model_name=runtime.gemini_report_model,
        )
        self.state.report_agent = report_result
        self.state.final_report = report_result.get("report") or {}

        arabic_pdf_report, translation_error = runtime.build_arabic_pdf_report(
            report_result.get("report") or {},
            api_key=runtime.gemini_api_key,
            model_name=runtime.gemini_report_model,
        )
        if translation_error:
            self.state.report_pdf_translation_error = translation_error

        try:
            report_pdf = runtime.save_report_pdf(
                arabic_pdf_report,
                upload_dir=runtime.upload_dir,
                submission_id=self.state.submission_id,
                patient_name=self.state.input_data.get("fullName") or self.state.input_data.get("full_name"),
                code_no=self.state.input_data.get("codeNo") or self.state.input_data.get("code_no"),
                arabic=True,
            )
            report_pdf["storage_backend"] = runtime.storage_backend
            report_pdf["ephemeral"] = runtime.storage_is_ephemeral
            self.state.report_pdf = report_pdf
        except (OSError, RuntimeError) as exc:
            self.state.report_pdf = {"error": str(exc)}

        self.state.stopped_after = "report_agent"
        return self.state.to_pipeline_result()

    @listen("stop_after_lifestyle")
    def finish_after_lifestyle(self):
        """Return the state snapshot for lifestyle-only cases."""
        return self.state.to_pipeline_result()


def run_crewai_workflow(
    data,
    submission_id=None,
    *,
    gemini_api_key,
    gemini_research_model,
    gemini_evidence_reviewer_model,
    gemini_report_model,
    clinical_agent_module,
    clinical_agent_dependencies,
    run_lifestyle_agent,
    run_research_agent,
    run_evidence_reviewer_agent,
    run_report_agent,
    build_arabic_pdf_report,
    save_report_pdf,
    upload_dir,
    storage_backend,
    storage_is_ephemeral,
):
    """Run the full CrewAI workflow through a Flow with structured state."""
    runtime = ClinicalFlowRuntime(
        gemini_api_key=gemini_api_key,
        gemini_research_model=gemini_research_model,
        gemini_evidence_reviewer_model=gemini_evidence_reviewer_model,
        gemini_report_model=gemini_report_model,
        clinical_agent_module=clinical_agent_module,
        clinical_agent_dependencies=clinical_agent_dependencies,
        run_lifestyle_agent=run_lifestyle_agent,
        run_research_agent=run_research_agent,
        run_evidence_reviewer_agent=run_evidence_reviewer_agent,
        run_report_agent=run_report_agent,
        build_arabic_pdf_report=build_arabic_pdf_report,
        save_report_pdf=save_report_pdf,
        upload_dir=upload_dir,
        storage_backend=storage_backend,
        storage_is_ephemeral=storage_is_ephemeral,
    )
    flow = ClinicalPipelineFlow(
        runtime=runtime,
        initial_state=ClinicalFlowState(
            submission_id=submission_id,
            input_data=dict(data or {}),
        ),
        suppress_flow_events=True,
    )
    flow.kickoff()
    return flow.state.to_pipeline_result()


run_full_clinical_pipeline = run_crewai_workflow
