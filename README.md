# Patient Intake Questionnaire

A bilingual medical intake web app for collecting patient questionnaire data, medication details, medical history, investigation results, and uploaded medical files.

The app is built with Flask, SQLite, HTML, CSS, and JavaScript. It includes optional medication lookup through openFDA, optional AI image scanning through OpenAI Vision, and optional DrugBank support when a DrugBank API key is available.
It also includes a local RAG index for clinical books and guidelines using Gemini embeddings.

## Features

- Bilingual English / Arabic intake questionnaire
- Client-side validation for required form fields
- SQLite storage for submitted intake forms
- Protected submissions page for reviewing saved forms
- Drug and package photo uploads
- Investigation image/PDF uploads
- Medication text entry for current medications
- Medical history and investigation result summaries
- openFDA drug label lookup
- Optional OpenAI Vision extraction from medication images
- Optional local OCR fallback with Pillow and pytesseract
- Optional DrugBank lookup when configured
- Local PDF RAG index for clinical guideline retrieval and citations

## Project Structure

```text
.
|-- app.py
|-- index.html
|-- script.js
|-- style.css
|-- requirements.txt
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
- Optional: Tesseract OCR installed on the operating system for local OCR fallback

Python packages are listed in `requirements.txt`.

## Setup

Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
pip install -r requirements.txt
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
OPENAI_API_KEY=your_openai_key
DRUGBANK_API_KEY=your_drugbank_key
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
```

These routes use the same HTTP Basic Auth password as `/submissions`.

## Medication Scanning

The medication upload section supports:

- Drug/package photos
- Current medication text
- Medical history summary
- Investigation/lab result summary
- Investigation files or photos

When the user clicks `Scan Uploads`, the server:

1. Saves uploaded files under `uploads/`.
2. Extracts medication text from images if OpenAI Vision or local OCR is configured.
3. Parses possible medication names from image text and manual medication text.
4. Looks up drug label data through openFDA.
5. Checks optional DrugBank data when `DRUGBANK_API_KEY` is set.
6. Stores the scan result with the normal form submission.

The scan is for intake documentation support only. Clinicians must confirm all medication names, doses, warnings, allergies, and interactions before using them for care decisions.

## Routes

```text
GET  /              Main intake form
GET  /style.css     Stylesheet
GET  /script.js     Browser logic
POST /submit        Save completed intake form
POST /scan-drugs    Upload files and run medication lookup
GET  /submissions   Password-protected submitted forms
GET  /uploads/...   Password-protected uploaded files
GET  /rag/status    Password-protected RAG index status
POST /rag/index     Password-protected RAG indexing
POST /rag/search    Password-protected RAG retrieval
POST /rag/context   Password-protected Clinical Agent context
```

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

## Optional OCR Notes

`pytesseract` is a Python wrapper. For OCR to work, the Tesseract executable must also be installed on the machine and available on the system path.

If OCR is not installed, the app still supports manual medication text and openFDA lookup.

## Development Notes

Useful checks:

```powershell
python -m py_compile app.py
```

Quick Flask smoke test:

```powershell
python -c "from app import app; c=app.test_client(); assert c.get('/').status_code == 200; print('ok')"
```
