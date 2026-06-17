"""Local RAG status and search routes."""

from flask import Blueprint, jsonify, request

from api.utils import clamp_int, deployment_info, password_required_response, submissions_authorized
from core.rag_store import build_clinical_context, index_rag_files, rag_status, search_rag


rag_bp = Blueprint("rag", __name__)


@rag_bp.route("/rag/status")
def rag_status_route():
    """Return the current indexing/search status for the local RAG document store."""
    if not submissions_authorized():
        return password_required_response()

    status = rag_status()
    status["deployment"] = deployment_info()
    return jsonify(status)


@rag_bp.route("/rag/index", methods=["POST"])
def rag_index_route():
    """Index uploaded/reference files into the local RAG store."""
    if not submissions_authorized():
        return password_required_response()

    options = request.get_json(silent=True) or {}
    try:
        result = index_rag_files(
            force=bool(options.get("force")),
            limit=options.get("limit"),
        )
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 400

    result["deployment"] = deployment_info()
    return jsonify(result)


@rag_bp.route("/rag/search", methods=["POST"])
def rag_search_route():
    """Search the local RAG store and return the most relevant source passages."""
    if not submissions_authorized():
        return password_required_response()

    data = request.get_json(silent=True) or {}
    query = str(data.get("query") or "").strip()
    if not query:
        return jsonify({"error": "query is required"}), 400

    top_k = clamp_int(data.get("top_k"), 6, 1, 12)
    try:
        result = search_rag(query, top_k=top_k)
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 400

    result["deployment"] = deployment_info()
    return jsonify(result)


@rag_bp.route("/rag/context", methods=["POST"])
def rag_context_route():
    """Build a combined clinical context block from the top RAG search results."""
    if not submissions_authorized():
        return password_required_response()

    data = request.get_json(silent=True) or {}
    query = str(data.get("query") or "").strip()
    if not query:
        return jsonify({"error": "query is required"}), 400

    top_k = clamp_int(data.get("top_k"), 6, 1, 12)
    try:
        result = build_clinical_context(query, top_k=top_k)
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 400

    result["deployment"] = deployment_info()
    return jsonify(result)
