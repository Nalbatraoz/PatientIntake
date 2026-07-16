# Patient Intake Questionnaire

A bilingual medical intake web app for collecting patient questionnaire data, medication details, medical history, investigation results, and uploaded medical files.

The app is built with Flask, SQLite, HTML, CSS, and JavaScript. It includes optional medication lookup through openFDA, local medication image OCR through Tesseract, and optional DrugBank support when a DrugBank API key is available.
It also includes a local RAG index for clinical books and guidelines using Gemini embeddings.

## Features

- Bilingual English / Arabic intake questionnaire
- Client-side validation for required form fields
- Visit types: `مسالك ذكورة / Urology & Andrology`, `كشف / Examination`, and doctor-launched `استشارة / Consultation` for returning patients
- Patient fills the main intake plus IIEF; PEDT, EHS, and Low Libido are doctor questionnaires launched from the protected submissions page
- SQLite storage for submitted intake forms
- Protected submissions page for reviewing saved forms, with phone number search and per-patient doctor actions
- Report-specific CrewAI chat for completed generated reports, with question-specific guideline (RAG) retrieval
- Drug and package photo uploads
- Investigation image/PDF uploads
- Medication text entry for current medications
- Medical history and investigation result summaries
- openFDA drug label lookup
- Local OCR extraction from medication images with Tesseract, Pillow, and pytesseract
- Gemini `gemini-2.5-flash-lite` image fallback when local OCR cannot read useful text
- Optional DrugBank lookup when configured
- Local PDF RAG index for clinical guideline retrieval and citations

## Project Structure

```text
.
|-- app.py
|-- clinical agent.py   # Clinical Agent orchestration for RAG and medication checks
|-- index.html
|-- script.js
|-- style.css
|-- pyproject.toml
|-- README.md
|-- rag_store.py         # PDF extraction, embedding, vector storage, and retrieval
|-- .gitignore
|-- APIkey              # local secrets file, ignored by git
|-- intake.db           # local SQLite database, ignored by git
|-- rag_vectors.db      # local RAG vector database, ignored by git
|-- RAG Files/          # local clinical source PDFs, ignored by git
`-- uploads/            # uploaded files, ignored by git
```

## Requirements

- Python 3.10 or newer
- pip
- Tesseract OCR installed on the operating system for medication image OCR

Python packages are listed in `pyproject.toml`.

## Setup

Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
python -m pip install -e .
```

Run the app:

```powershell
python app.py
```

Open the app:

```text
http://127.0.0.1:5000/
```

## API Keys

The app reads API keys from environment variables first. If they are not set, it reads them from a local `APIkey` file in the project folder.

Supported keys:

```text
OPENFDA_API_KEY=your_openfda_key
GEMINI_API_KEY=your_gemini_key
```

For openFDA only, `APIkey` may also contain just the bare key:

```text
your_openfda_key
```

`APIkey` is listed in `.gitignore` and should not be committed.

## Clinical Books RAG

Place source PDFs in:

```text
RAG Files/
```

Index the PDFs into the local SQLite vector store:

```powershell
python rag_store.py index
```

The indexer:

1. Extracts text from PDFs with `pypdf`.
2. Splits each page into overlapping chunks.
3. Creates Gemini embeddings with `gemini-embedding-001`.
4. Stores vectors and source metadata in `rag_vectors.db`.
5. Preserves filename and page number for citations.

Check index status:

```powershell
python rag_store.py status
```

Search the indexed books:

```powershell
python rag_store.py search "erectile dysfunction initial evaluation" --top-k 6
```

The Flask API also exposes protected RAG routes:

```text
GET  /rag/status    RAG index status
POST /rag/index     Build or refresh the local vector index
POST /rag/search    Search books and return passages with citations
POST /rag/context   Return prompt-ready context for a Clinical Agent
POST /clinical-agent Build a clinician-review packet from RAG plus medication checks
```

These routes use the same HTTP Basic Auth password as `/submissions`.

## Clinical Agent

The protected `/clinical-agent` endpoint uses Gemini as the reasoning layer over an evidence packet that combines:

1. Local RAG guideline retrieval from `rag_vectors.db`.
2. Medication name parsing from supplied medication/history text.
3. openFDA drug label checks.
5. Gemini-generated structured clinical review with citations, medication flags, and safety notes.

The Gemini model defaults to `gemini-2.5-flash` and can be changed with:

```text
GEMINI_CLINICAL_MODEL=your_model_name
```

Example request body:

```json
{
  "query": "erectile dysfunction initial evaluation and medication safety",
  "current_medications": "sildenafil, nitroglycerin",
  "medical_history": "ischemic heart disease",
  "top_k": 4
}
```

You can also pass a saved intake form:

```json
{
  "submission_id": 1,
  "query": "review this case for guideline context and medication safety"
}
```

The endpoint supports clinical review only. It does not diagnose, prescribe, or replace clinician judgment.

## Report-Specific Chat

Completed submissions expose an `Ask about this report` panel on `/submissions`.
The panel sends the selected card's `submission_id`, so the doctor does not need to type the patient code.

The protected report chat API uses the configured `DB_PATH` database, including EC2 deployments such as:

```text
DB_PATH=/home/ec2-user/PatientIntake/intake.db
```

It loads exactly one submission row and answers only from `form_data.clinical_pipeline.report_agent`, especially the saved final report and report packet. It does not read other patients, other reports, raw upstream pipeline branches, or fresh RAG context. If patient answers, uploaded files, extracted text, or photos are not represented in the saved report-agent output, the chat agent says the evidence is unavailable.

Routes:

```text
GET  /report-chat/history?submission_id=20
POST /report-chat
```

Example request:

```json
{
  "submission_id": "INT-20",
  "question": "Why was this flag raised?"
}
```

The response contains a direct answer, reasoning summary, references, uncertainty, and limitations. Chat exchanges are saved to `report_chat_messages` for audit history scoped by `submission_id`.

## Patient And Doctor Forms

The intake is split between the patient and the doctor:

1. The patient completes the main questionnaire and is then redirected to the IIEF questionnaire. The intake is marked complete (and the doctor is notified) once IIEF is submitted.
2. PEDT, EHS, and Low Libido are doctor questionnaires. They are password-protected and launched per patient from the `Doctor actions` row on each submission card (`?mode=doctor`). Forms suggested by the patient's complaints are marked `needed`; already-filled forms show a check mark.
3. Consultation visits (`استشارة`) are for returning patients only. The consultation visit type is hidden on the public intake page and is launched from the submissions page, which opens the intake pre-set to the existing patient's code.

The submissions page also supports searching by phone number (Arabic-Indic digits accepted), patient name, or code.

## Submit Workflow

When a patient submits the main questionnaire, the app now follows the clinical workflow:

1. Save the form to `intake.db`.
2. Run the Gemini Lifestyle Agent.
3. If lifestyle is sufficient to explain symptoms, stop and return the lifestyle report.
4. If lifestyle is not sufficient, run medication checks through openFDA.
5. Retrieve guideline context from the local vector database.
6. Send medication and RAG evidence to the Gemini Clinical Agent.
7. Search PubMed for relevant research papers.
8. Send the Clinical Agent packet and PubMed evidence to the Gemini Research Agent.
9. Store the workflow result inside the saved submission under `clinical_pipeline`.

The browser submit modal shows a short workflow summary after submission. Full details are saved with the submission record.

## Medication Scanning

The medication upload section supports:

- Drug/package photos
- Current medication text
- Medical history summary
- Investigation/lab result summary
- Investigation files or photos

When the user clicks `Scan Uploads`, the server:

1. Saves uploaded files under `uploads/`.
2. Extracts medication text from drug/package images with local Tesseract OCR.
3. If local OCR does not return useful text, asks Gemini `gemini-2.5-flash-lite` to describe the image and extract visible label text.
4. Parses possible medication names from image text and manual medication text.
5. Looks up drug label data through openFDA.
6. Stores the scan result with the normal form submission.

The scan is for intake documentation support only. Clinicians must confirm all medication names, doses, warnings, allergies, and interactions before using them for care decisions.

## Routes

```text
GET  /              Main intake form
GET  /style.css     Stylesheet
GET  /script.js     Browser logic
POST /submit        Save completed intake form
GET  /iief          Patient IIEF questionnaire
GET  /pedt          Password-protected doctor PEDT questionnaire
GET  /ehs           Password-protected doctor Erection Hardness Scale
GET  /low-libido    Password-protected doctor Low Libido questionnaire
POST /scan-drugs    Upload files and run medication lookup
GET  /submissions   Password-protected submitted forms
GET  /uploads/...   Password-protected uploaded files
GET  /rag/status    Password-protected RAG index status
POST /rag/index     Password-protected RAG indexing
POST /rag/search    Password-protected RAG retrieval
POST /rag/context   Password-protected Clinical Agent context
POST /clinical-agent Password-protected RAG plus medication-check agent
GET  /report-chat/history Password-protected report chat history for one completed report
POST /report-chat   Password-protected report-specific CrewAI chat
```

## Deploying To AWS EC2 (Persistent Server)

To deploy to AWS EC2 or another persistent server:

1. Clone this repository on your instance.
2. Set up a systemd service (or run with gunicorn/uwsgi) to keep the Flask app running persistently.
3. Install Tesseract OCR on the instance and make sure the `tesseract` command is on PATH, or set `TESSERACT_CMD=/usr/bin/tesseract`.
4. Configure your environment variables or local `APIkey` file (including `GEMINI_API_KEY`).
5. Ensure the database (`intake.db`), RAG vectors (`rag_vectors.db`), and `uploads/` directory have write permissions.
6. In a persistent VM environment, background threads spawned by Flask (such as the clinical pipeline running CrewAI and Gemini agents) will run continuously until completion.

## Submitted Forms

Submitted forms are stored in `intake.db`.

View submissions:

```text
http://127.0.0.1:5000/submissions
```

The page uses HTTP Basic Auth. The password is controlled by:

```text
SUBMISSIONS_PASSWORD=your_password
```

If not set, the default password is:

```text
Doctor
```

## Local Data And Privacy

This app stores sensitive medical information locally:

- `intake.db`
- `uploads/`
- `APIkey`
- `rag_vectors.db`
- `RAG Files/`
- generated logs

These files are ignored by git. Do not deploy this app publicly without adding proper production security, HTTPS, authentication, authorization, access logging, backups, and clinical data privacy controls.

## OCR Notes

`pytesseract` is a Python wrapper. For OCR to work, the Tesseract executable must also be installed on the machine and available on the system path.

On Amazon Linux / EC2, install the operating-system package first, for example:

```bash
sudo dnf install -y tesseract
```

On Ubuntu/Debian EC2 images:

```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr
```

The app auto-detects Tesseract in this order:

1. `TESSERACT_CMD` environment variable
2. `tesseract` on PATH
3. Common Windows install folders
4. `/usr/bin/tesseract`
5. `/usr/local/bin/tesseract`

If `tesseract --version` works in the same environment that runs the app, no code change or `TESSERACT_CMD` setting is required.

If Tesseract is not on PATH, set:

```text
TESSERACT_CMD=/usr/bin/tesseract
```

The default OCR language is English:

```text
TESSERACT_LANG=eng
```

For Arabic OCR, install the Arabic language data on the server and set:

```text
TESSERACT_LANG=eng+ara
```

If local OCR is not installed and Gemini fallback is not configured, the app still supports manual medication text and openFDA lookup.

When Tesseract runs but does not return useful text, the app can fall back to Gemini image extraction. This uses the existing `GEMINI_API_KEY` and defaults to:

```text
GEMINI_OCR_MODEL=gemini-2.5-flash-lite
```

## Development Notes

Useful checks:

```powershell
python -m py_compile app.py
```

Quick Flask smoke test:

```powershell
python -c "from app import app; c=app.test_client(); assert c.get('/').status_code == 200; print('ok')"
```
