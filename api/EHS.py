"""Erection Hardness Scale routes."""

from flask import Blueprint, send_from_directory

from api.utils import FRONTEND_DIR


ehs_bp = Blueprint("ehs", __name__)


@ehs_bp.route("/ehs")
def ehs_page():
    """Serve the Erection Hardness Scale page."""
    return send_from_directory(FRONTEND_DIR, "ehs.html")


@ehs_bp.route("/ehs.css")
def ehs_css():
    """Serve the Erection Hardness Scale stylesheet."""
    return send_from_directory(FRONTEND_DIR, "ehs.css")


@ehs_bp.route("/ehs.js")
def ehs_js():
    """Serve the Erection Hardness Scale JavaScript logic."""
    return send_from_directory(FRONTEND_DIR, "ehs.js")

