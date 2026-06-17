"""Flask application entrypoint for the patient intake API."""

import os

from flask import Flask
from flask_cors import CORS

from api.EHS import ehs_bp
from api.Notifications import notifications_bp
from api.clinical_agent_routes import clinical_agent_bp
from api.drug_scan_routes import drug_scan_bp
from api.form_routes import form_bp
from api.iief import iief_bp
from api.low_libido import low_libido_bp
from api.patient_routes import patient_bp
from api.pedt import pedt_bp
from api.rag_routes import rag_bp
from api.submissions_routes import submissions_bp
from api.utils import init_db


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class _PrefixMiddleware:
    """Allow the app to live behind a reverse-proxy path prefix."""

    def __init__(self, app, prefix):
        self.app = app
        self.prefix = prefix.rstrip("/")

    def __call__(self, environ, start_response):
        prefix = self.prefix
        path_info = environ.get("PATH_INFO", "")
        if prefix and (path_info == prefix or path_info.startswith(prefix + "/")):
            environ["SCRIPT_NAME"] = environ.get("SCRIPT_NAME", "") + prefix
            stripped = path_info[len(prefix):]
            environ["PATH_INFO"] = stripped if stripped else "/"
        return self.app(environ, start_response)


app = Flask(__name__, template_folder=os.path.join(BASE_DIR, "frontend"))

_APP_BASE_PATH = os.environ.get("APP_BASE_PATH", "").strip()
if _APP_BASE_PATH and _APP_BASE_PATH != "/":
    _APP_BASE_PATH = "/" + _APP_BASE_PATH.strip("/")
else:
    _APP_BASE_PATH = ""

if _APP_BASE_PATH:
    app.config["APPLICATION_ROOT"] = _APP_BASE_PATH
    app.wsgi_app = _PrefixMiddleware(app.wsgi_app, _APP_BASE_PATH)

CORS(app)
app.config["MAX_CONTENT_LENGTH"] = 30 * 1024 * 1024

app.register_blueprint(form_bp)
app.register_blueprint(patient_bp)
app.register_blueprint(drug_scan_bp)
app.register_blueprint(submissions_bp)
app.register_blueprint(rag_bp)
app.register_blueprint(notifications_bp)
app.register_blueprint(clinical_agent_bp)
app.register_blueprint(ehs_bp)
app.register_blueprint(low_libido_bp)
app.register_blueprint(pedt_bp)
app.register_blueprint(iief_bp)


if __name__ == "__main__":
    init_db()
    debug_mode = os.environ.get("FLASK_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}
    host = os.environ.get("FLASK_HOST", "0.0.0.0").strip() or "0.0.0.0"
    port = int(os.environ.get("FLASK_PORT", "5001"))
    app.run(host=host, port=port, debug=debug_mode, use_reloader=False)
