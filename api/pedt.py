"""PEDT questionnaire routes."""

from flask import Blueprint, send_from_directory

from api.utils import FRONTEND_DIR


pedt_bp = Blueprint("pedt", __name__)


@pedt_bp.route("/pedt")
def pedt_page():
    """Serve the PEDT questionnaire page."""
    return send_from_directory(FRONTEND_DIR, "pedt.html")


@pedt_bp.route("/pedt.css")
def pedt_css():
    """Serve the PEDT questionnaire stylesheet."""
    return send_from_directory(FRONTEND_DIR, "pedt.css")


@pedt_bp.route("/pedt.js")
def pedt_js():
    """Serve the PEDT questionnaire JavaScript logic."""
    return send_from_directory(FRONTEND_DIR, "pedt.js")

