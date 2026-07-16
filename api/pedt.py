"""PEDT questionnaire routes (doctor-only, filled from the submissions page)."""

from flask import Blueprint, send_from_directory

from api.utils import FRONTEND_DIR, password_required_response, submissions_authorized


pedt_bp = Blueprint("pedt", __name__)


@pedt_bp.route("/pedt")
def pedt_page():
    """Serve the doctor-only PEDT questionnaire page."""
    if not submissions_authorized():
        return password_required_response()
    return send_from_directory(FRONTEND_DIR, "pedt.html")


@pedt_bp.route("/pedt.css")
def pedt_css():
    """Serve the PEDT questionnaire stylesheet."""
    return send_from_directory(FRONTEND_DIR, "pedt.css")


@pedt_bp.route("/pedt.js")
def pedt_js():
    """Serve the PEDT questionnaire JavaScript logic."""
    return send_from_directory(FRONTEND_DIR, "pedt.js")

