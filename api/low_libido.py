"""Low Libido questionnaire routes."""

from flask import Blueprint, send_from_directory

from api.utils import FRONTEND_DIR


low_libido_bp = Blueprint("low_libido", __name__)


@low_libido_bp.route("/low-libido")
def low_libido_page():
    """Serve the Low Libido Questionnaire page."""
    return send_from_directory(FRONTEND_DIR, "low-libido.html")


@low_libido_bp.route("/low-libido.css")
def low_libido_css():
    """Serve the Low Libido Questionnaire stylesheet."""
    return send_from_directory(FRONTEND_DIR, "low-libido.css")


@low_libido_bp.route("/low-libido.js")
def low_libido_js():
    """Serve the Low Libido Questionnaire JavaScript logic."""
    return send_from_directory(FRONTEND_DIR, "low-libido.js")

