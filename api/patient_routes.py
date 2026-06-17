"""Patient code lookup routes."""

from flask import Blueprint, jsonify, request

from api.utils import generate_next_patient_code, get_patient_by_code


patient_bp = Blueprint("patient", __name__)


@patient_bp.route("/patient-code/next")
def generate_patient_code():
    """Generate and return the next available patient code."""
    code_no = generate_next_patient_code()
    return jsonify({
        "codeNo": code_no,
        "message": f"Generated new patient code: {code_no}",
    })


@patient_bp.route("/patient-code/<code>")
def lookup_patient_code(code):
    """Look up an existing patient by their code."""
    password = request.args.get("password") or ""
    patient = get_patient_by_code(code, password=password)

    if not patient:
        return jsonify({
            "found": False,
            "error": "Patient record not found or password is incorrect.",
        }), 401

    return jsonify({
        "found": True,
        "codeNo": patient["codeNo"],
        "full_name": patient["full_name"],
        "name": patient["full_name"],
        "age": patient["age"],
        "mobile": patient["mobile"],
        "phone": patient["mobile"],
        "email": patient["email"],
        "form_data": patient["form_data"],
    })


@patient_bp.route("/patient-code/lookup", methods=["POST"])
def lookup_patient_code_with_password():
    """Look up a patient record using their code and patient password."""
    data = request.get_json(silent=True) or {}
    code = str(data.get("codeNo") or data.get("code") or "").strip()
    password = str(data.get("password") or "").strip()

    if not code:
        return jsonify({"found": False, "error": "Patient code is required."}), 400

    patient = get_patient_by_code(code, password=password)
    if not patient:
        return jsonify({
            "found": False,
            "error": "Patient record not found or password is incorrect.",
        }), 401

    return jsonify({
        "found": True,
        "codeNo": patient["codeNo"],
        "full_name": patient["full_name"],
        "name": patient["full_name"],
        "age": patient["age"],
        "mobile": patient["mobile"],
        "phone": patient["mobile"],
        "email": patient["email"],
        "form_data": patient["form_data"],
    })
