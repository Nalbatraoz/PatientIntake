"""Drug scan upload and openFDA routes."""

from flask import Blueprint, jsonify, request

from api.utils import (
    ALLOWED_IMAGE_EXTENSIONS,
    ALLOWED_INVESTIGATION_EXTENSIONS,
    MAX_LOOKUP_NAMES,
    MAX_UPLOAD_FILES,
    build_label_flags,
    deployment_info,
    extract_text_with_gemini,
    extract_text_with_tesseract,
    first_text,
    has_useful_ocr_text,
    lookup_openfda_label,
    parse_possible_drug_names,
    save_uploaded_file,
)


drug_scan_bp = Blueprint("drug_scan", __name__)


def _unique_drug_candidates(*candidate_groups):
    drug_candidates = []
    seen = set()
    for name in (item for group in candidate_groups for item in group):
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        drug_candidates.append(name)
        if len(drug_candidates) >= MAX_LOOKUP_NAMES:
            break
    return drug_candidates


def _label_summary(openfda_results, drug_candidates):
    matched_labels = [result for result in openfda_results if result.get("found")]
    if matched_labels:
        return [{
            "type": "label_summary",
            "message": (
                f"Reviewed {len(matched_labels)} medication label(s) for the submitted image "
                "and found no direct warning or interaction text matches."
            ),
        }]
    if drug_candidates:
        return [{
            "type": "label_summary",
            "message": (
                f"Looked up {len(drug_candidates)} medication candidate(s) from the submitted image "
                "and found no openFDA label matches."
            ),
        }]
    return []


def _scan_notes(drug_image_count, ocr_scan, gemini_note, current_medications, extracted_text, extracted_description):
    notes = []
    if drug_image_count:
        notes.append(f"Scanned {drug_image_count} uploaded drug image(s) from the submitted form.")
    if ocr_scan:
        notes.append(f"Scan source: {'Gemini vision' if gemini_note else 'Local OCR'}.")
    elif current_medications.strip():
        notes.append("Medication text was scanned from the form instead of an uploaded image.")
    if extracted_text.strip():
        notes.append("Readable text was extracted from the submitted image.")
    if extracted_description.strip():
        notes.append(f"Image description: {extracted_description}")
    return notes


@drug_scan_bp.route("/scan-drugs", methods=["POST"])
def scan_drugs():
    """Handle medication image uploads, OCR them, and run openFDA checks."""
    saved_files = []
    errors = []

    upload_groups = [
        ("drugImages", "drug-images", ALLOWED_IMAGE_EXTENSIONS),
        ("investigationFiles", "investigations", ALLOWED_INVESTIGATION_EXTENSIONS),
    ]

    for field_name, category, allowed_extensions in upload_groups:
        for file_obj in request.files.getlist(field_name)[:MAX_UPLOAD_FILES]:
            try:
                saved = save_uploaded_file(file_obj, category, allowed_extensions)
                if saved:
                    saved_files.append(saved)
            except ValueError as exc:
                errors.append(str(exc))

    current_medications = request.form.get("currentMedications", "")
    medical_history = request.form.get("medicalHistory", "")

    has_drug_images = any(file_info.get("category") == "drug-images" for file_info in saved_files)
    drug_image_count = sum(1 for file_info in saved_files if file_info.get("category") == "drug-images")
    gemini_note = None
    ocr_scan = None

    if has_drug_images:
        ocr_scan, _ = extract_text_with_tesseract(saved_files)
        if not has_useful_ocr_text(ocr_scan):
            ocr_scan, gemini_note = extract_text_with_gemini(saved_files)

    extracted_text = ""
    extracted_description = ""
    extracted_names = []
    scan_source = "manual_text"

    if ocr_scan:
        scan_source = "gemini_vision" if gemini_note else "local_ocr"
        extracted_text = first_text(ocr_scan.get("observed_text"), 2000)
        extracted_description = first_text(ocr_scan.get("image_description"), 1000)
        extracted_names = [
            str(name).strip()
            for name in ocr_scan.get("drug_names", [])
            if str(name).strip()
        ]

    drug_candidates = _unique_drug_candidates(
        extracted_names,
        parse_possible_drug_names(current_medications, extracted_text),
    )
    openfda_results = [lookup_openfda_label(name) for name in drug_candidates]
    label_flags = build_label_flags(openfda_results, current_medications, medical_history)
    if not label_flags:
        label_flags = _label_summary(openfda_results, drug_candidates)

    return jsonify({
        "message": "Upload received and medication lookup completed. / طھظ… ط§ط³طھظ„ط§ظ… ط§ظ„ظ…ظ„ظپط§طھ ظˆط¥ظƒظ…ط§ظ„ ط§ظ„ط¨ط­ط« ط¹ظ† ط§ظ„ط£ط¯ظˆظٹط©.",
        "files": saved_files,
        "scan_source": scan_source,
        "extracted_text": extracted_text,
        "image_description": extracted_description,
        "drug_candidates": drug_candidates,
        "openfda": openfda_results,
        "label_flags": label_flags,
        "notes": _scan_notes(
            drug_image_count,
            ocr_scan,
            gemini_note,
            current_medications,
            extracted_text,
            extracted_description,
        ),
        "deployment": deployment_info(),
    })
