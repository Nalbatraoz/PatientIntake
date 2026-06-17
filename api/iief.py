"""IIEF questionnaire routes."""

from flask import Blueprint, send_from_directory

from api.utils import FRONTEND_DIR


iief_bp = Blueprint("iief", __name__)


@iief_bp.route("/iief")
def iief_page():
    """Serve the IIEF Questionnaire page."""
    return send_from_directory(FRONTEND_DIR, "iief.html")


@iief_bp.route("/iief.css")
def iief_css():
    """Serve the IIEF Questionnaire stylesheet."""
    return send_from_directory(FRONTEND_DIR, "iief.css")


@iief_bp.route("/iief.js")
def iief_js():
    """Serve the IIEF Questionnaire JavaScript logic."""
    return send_from_directory(FRONTEND_DIR, "iief.js")

