"""Clinical agent test and execution routes."""

from flask import Blueprint, jsonify, render_template, request

from api.utils import clinical_agent_dependencies, clinical_agent_module, deployment_info, password_required_response, submissions_authorized


clinical_agent_bp = Blueprint("clinical_agent", __name__)


@clinical_agent_bp.route("/clinical-agent-test")
def clinical_agent_test_page():
    """Serve a protected browser test page for calling the clinical agent endpoint."""
    if not submissions_authorized():
        return password_required_response()

    return render_template("clinical-agent-test.html")


@clinical_agent_bp.route("/clinical-agent", methods=["POST"])
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

