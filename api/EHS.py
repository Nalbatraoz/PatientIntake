"""Erection Hardness Scale routes (doctor-only, filled from the submissions page)."""

from flask import Blueprint, send_from_directory

from api.utils import FRONTEND_DIR, password_required_response, submissions_authorized


ehs_bp = Blueprint("ehs", __name__)


@ehs_bp.route("/ehs")
def ehs_page():
    """Serve the doctor-only Erection Hardness Scale page."""
    if not submissions_authorized():
        return password_required_response()
    return send_from_directory(FRONTEND_DIR, "ehs.html")


@ehs_bp.route("/ehs.css")
def ehs_css():
    """Serve the Erection Hardness Scale stylesheet."""
    return send_from_directory(FRONTEND_DIR, "ehs.css")


@ehs_bp.route("/ehs.js")
def ehs_js():
    """Serve the Erection Hardness Scale JavaScript logic."""
    return send_from_directory(FRONTEND_DIR, "ehs.js")

