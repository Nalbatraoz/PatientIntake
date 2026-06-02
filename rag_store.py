import argparse
import array
import hashlib
import json
import math
import os
import re
import sqlite3
import sys
import time
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RAG_SOURCE_DIR = os.environ.get("RAG_SOURCE_DIR", os.path.join(BASE_DIR, "RAG Files"))
RAG_DB_PATH = os.environ.get("RAG_DB_PATH", os.path.join(BASE_DIR, "rag_vectors.db"))
GEMINI_EMBEDDING_MODEL = os.environ.get("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
GEMINI_EMBEDDING_DIM = int(os.environ.get("GEMINI_EMBEDDING_DIM", "768"))
CHUNK_MAX_CHARS = int(os.environ.get("RAG_CHUNK_MAX_CHARS", "2400"))
CHUNK_OVERLAP_CHARS = int(os.environ.get("RAG_CHUNK_OVERLAP_CHARS", "300"))
EMBEDDING_BATCH_SIZE = int(os.environ.get("RAG_EMBEDDING_BATCH_SIZE", "16"))
REQUEST_TIMEOUT_SECONDS = int(os.environ.get("RAG_REQUEST_TIMEOUT_SECONDS", "45"))


def utc_now():
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def load_secret(name):
    value = os.environ.get(name)
    if value:
        return value.strip()

    secret_path = os.path.join(BASE_DIR, "APIkey")
    aliases = {
        "GEMINI_API_KEY": {"GEMINI_API_KEY", "GOOGLE_API_KEY", "GEMINI", "GOOGLE"},
    }

    try:
        with open(secret_path, "r", encoding="utf-8") as secret_file:
            lines = [
                line.strip()
                for line in secret_file
                if line.strip() and not line.lstrip().startswith("#")
            ]
    except OSError:
        return None

    valid_names = aliases.get(name, {name})
    for line in lines:
        if "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        if key.strip().upper() in valid_names:
            return raw_value.strip().strip("\"'")

    if name == "GEMINI_API_KEY" and len(lines) == 1 and lines[0].startswith("AIza"):
        return lines[0].strip().strip("\"'")

    return None


def model_resource_name():
    if GEMINI_EMBEDDING_MODEL.startswith("models/"):
        return GEMINI_EMBEDDING_MODEL
    return f"models/{GEMINI_EMBEDDING_MODEL}"


def normalize_text(text):
    text = re.sub(r"\r\n?", "\n", text or "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as file_obj:
        for block in iter(lambda: file_obj.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def relative_source_path(path):
    return os.path.relpath(path, BASE_DIR).replace(os.sep, "/")


def list_pdf_files(source_dir=RAG_SOURCE_DIR):
    if not os.path.isdir(source_dir):
        return []

    paths = []
    for root, _, filenames in os.walk(source_dir):
        for filename in filenames:
            if filename.lower().endswith(".pdf"):
                paths.append(os.path.join(root, filename))
    return sorted(paths, key=lambda item: item.lower())


def extract_pdf_pages(path):
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("Install pypdf first: pip install -r requirements.txt") from exc

    reader = PdfReader(path)
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception:
            pass

    pages = []
    for index, page in enumerate(reader.pages, start=1):
        try:
            text = normalize_text(page.extract_text() or "")
        except Exception:
            text = ""
        if text:
            pages.append({"page_number": index, "text": text})

    return pages, len(reader.pages)


def split_text_into_chunks(text, max_chars=CHUNK_MAX_CHARS, overlap_chars=CHUNK_OVERLAP_CHARS):
    words = text.split()
    chunks = []
    current = []
    current_len = 0

    for word in words:
        addition = len(word) + (1 if current else 0)
        if current and current_len + addition > max_chars:
            chunks.append(" ".join(current))
            overlap = []
            overlap_len = 0
            for previous in reversed(current):
                previous_addition = len(previous) + (1 if overlap else 0)
                if overlap and overlap_len + previous_addition > overlap_chars:
                    break
                overlap.insert(0, previous)
                overlap_len += previous_addition
            current = overlap
            current_len = overlap_len

        current.append(word)
        current_len += len(word) + (1 if current_len else 0)

    if current:
        chunks.append(" ".join(current))

    return [chunk for chunk in chunks if chunk.strip()]


def build_document_chunks(path):
    pages, page_count = extract_pdf_pages(path)
    chunks = []

    for page in pages:
        for chunk_text in split_text_into_chunks(page["text"]):
            chunks.append({
                "page_number": page["page_number"],
                "text": chunk_text,
            })

    return chunks, page_count


def request_json(url, *, method="POST", headers=None, body=None, timeout=REQUEST_TIMEOUT_SECONDS):
    request_headers = {"Accept": "application/json"}
    if headers:
        request_headers.update(headers)

    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        request_headers["Content-Type"] = "application/json"

    req = Request(url, data=data, headers=request_headers, method=method)
    with urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def extract_embedding_values(item):
    if isinstance(item.get("values"), list):
        return item["values"]
    embedding = item.get("embedding")
    if isinstance(embedding, dict) and isinstance(embedding.get("values"), list):
        return embedding["values"]
    raise RuntimeError("Gemini embedding response did not include embedding values.")


def gemini_embed_texts(texts, *, task_type, title=None, api_key=None):
    if not texts:
        return []

    api_key = api_key or load_secret("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured in the environment or APIkey file.")

    model_name = model_resource_name()
    url = f"https://generativelanguage.googleapis.com/v1beta/{model_name}:batchEmbedContents"
    config = {
        "taskType": task_type,
        "autoTruncate": True,
        "outputDimensionality": GEMINI_EMBEDDING_DIM,
    }
    if title and task_type == "RETRIEVAL_DOCUMENT":
        config["title"] = title

    body = {
        "requests": [
            {
                "model": model_name,
                "content": {"parts": [{"text": text}]},
                "embedContentConfig": config,
            }
            for text in texts
        ]
    }

    last_error = None
    for attempt in range(3):
        try:
            payload = request_json(
                url,
                headers={"x-goog-api-key": api_key},
                body=body,
            )
            embeddings = payload.get("embeddings") or []
            if len(embeddings) != len(texts):
                raise RuntimeError(
                    f"Gemini returned {len(embeddings)} embeddings for {len(texts)} texts."
                )
            return [extract_embedding_values(item) for item in embeddings]
        except HTTPError as exc:
            last_error = f"Gemini embedding HTTP {exc.code}"
            if exc.code not in {429, 500, 502, 503, 504}:
                try:
                    detail = exc.read().decode("utf-8")
                except Exception:
                    detail = ""
                raise RuntimeError(f"{last_error}: {detail}") from exc
        except (URLError, TimeoutError, json.JSONDecodeError, RuntimeError) as exc:
            last_error = str(exc)

        time.sleep(2 ** attempt)

    raise RuntimeError(f"Gemini embedding request failed after retries: {last_error}")


def pack_embedding(values):
    return array.array("f", [float(value) for value in values]).tobytes()


def unpack_embedding(blob):
    values = array.array("f")
    values.frombytes(blob)
    return values


def vector_norm(values):
    return math.sqrt(sum(float(value) * float(value) for value in values))


def connect_rag_db(path=RAG_DB_PATH):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    init_rag_db(conn)
    return conn


def init_rag_db(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS rag_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_path TEXT NOT NULL UNIQUE,
            filename TEXT NOT NULL,
            sha256 TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            page_count INTEGER NOT NULL DEFAULT 0,
            indexed_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS rag_chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            chunk_index INTEGER NOT NULL,
            page_number INTEGER NOT NULL,
            text TEXT NOT NULL,
            embedding BLOB NOT NULL,
            embedding_dim INTEGER NOT NULL,
            embedding_norm REAL NOT NULL,
            embedding_model TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (document_id) REFERENCES rag_documents(id) ON DELETE CASCADE,
            UNIQUE (document_id, chunk_index, embedding_model, embedding_dim)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_rag_chunks_model ON rag_chunks (embedding_model, embedding_dim)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_rag_chunks_document ON rag_chunks (document_id)")
    conn.commit()


def existing_document(conn, source_path):
    return conn.execute(
        "SELECT * FROM rag_documents WHERE source_path = ?",
        (source_path,),
    ).fetchone()


def current_chunk_count(conn, document_id):
    return conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM rag_chunks
        WHERE document_id = ?
          AND embedding_model = ?
          AND embedding_dim = ?
        """,
        (document_id, GEMINI_EMBEDDING_MODEL, GEMINI_EMBEDDING_DIM),
    ).fetchone()["count"]


def replace_document_chunks(conn, *, document, chunks, embedded_rows, page_count):
    source_path = document["source_path"]
    existing = existing_document(conn, source_path)
    now = utc_now()

    if existing:
        document_id = existing["id"]
        conn.execute("DELETE FROM rag_chunks WHERE document_id = ?", (document_id,))
        conn.execute(
            """
            UPDATE rag_documents
            SET filename = ?, sha256 = ?, file_size = ?, page_count = ?, indexed_at = ?
            WHERE id = ?
            """,
            (
                document["filename"],
                document["sha256"],
                document["file_size"],
                page_count,
                now,
                document_id,
            ),
        )
    else:
        cursor = conn.execute(
            """
            INSERT INTO rag_documents (source_path, filename, sha256, file_size, page_count, indexed_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                source_path,
                document["filename"],
                document["sha256"],
                document["file_size"],
                page_count,
                now,
            ),
        )
        document_id = cursor.lastrowid

    rows = []
    for index, (chunk, embedding) in enumerate(zip(chunks, embedded_rows), start=1):
        norm = vector_norm(embedding)
        if norm == 0:
            continue
        rows.append((
            document_id,
            index,
            chunk["page_number"],
            chunk["text"],
            pack_embedding(embedding),
            len(embedding),
            norm,
            GEMINI_EMBEDDING_MODEL,
            now,
        ))

    conn.executemany(
        """
        INSERT INTO rag_chunks (
            document_id, chunk_index, page_number, text, embedding,
            embedding_dim, embedding_norm, embedding_model, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()
    return len(rows)


def batch_items(items, batch_size):
    for start in range(0, len(items), batch_size):
        yield items[start:start + batch_size]


def index_rag_files(*, source_dir=RAG_SOURCE_DIR, force=False, limit=None):
    pdf_paths = list_pdf_files(source_dir)
    if limit is not None:
        pdf_paths = pdf_paths[:int(limit)]
    if pdf_paths and not load_secret("GEMINI_API_KEY"):
        raise RuntimeError("GEMINI_API_KEY is not configured in the environment or APIkey file.")

    summary = {
        "source_dir": source_dir,
        "database": RAG_DB_PATH,
        "embedding_model": GEMINI_EMBEDDING_MODEL,
        "embedding_dim": GEMINI_EMBEDDING_DIM,
        "files_found": len(pdf_paths),
        "files_indexed": 0,
        "files_skipped": 0,
        "files_failed": 0,
        "chunks_indexed": 0,
        "documents": [],
    }

    with connect_rag_db() as conn:
        for path in pdf_paths:
            source_path = relative_source_path(path)
            filename = os.path.basename(path)
            file_hash = sha256_file(path)
            file_size = os.path.getsize(path)
            existing = existing_document(conn, source_path)

            if (
                existing
                and existing["sha256"] == file_hash
                and current_chunk_count(conn, existing["id"]) > 0
                and not force
            ):
                count = current_chunk_count(conn, existing["id"])
                summary["files_skipped"] += 1
                summary["documents"].append({
                    "file": source_path,
                    "status": "skipped",
                    "chunks": count,
                })
                continue

            try:
                chunks, page_count = build_document_chunks(path)
                embedded_rows = []
                for batch in batch_items(chunks, EMBEDDING_BATCH_SIZE):
                    texts = [chunk["text"] for chunk in batch]
                    embedded_rows.extend(
                        gemini_embed_texts(texts, task_type="RETRIEVAL_DOCUMENT", title=filename)
                    )

                document = {
                    "source_path": source_path,
                    "filename": filename,
                    "sha256": file_hash,
                    "file_size": file_size,
                }
                indexed_count = replace_document_chunks(
                    conn,
                    document=document,
                    chunks=chunks,
                    embedded_rows=embedded_rows,
                    page_count=page_count,
                )
                summary["files_indexed"] += 1
                summary["chunks_indexed"] += indexed_count
                summary["documents"].append({
                    "file": source_path,
                    "status": "indexed",
                    "pages": page_count,
                    "chunks": indexed_count,
                })
            except Exception as exc:
                summary["files_failed"] += 1
                summary["documents"].append({
                    "file": source_path,
                    "status": "failed",
                    "error": str(exc),
                })

    return summary


def rag_status():
    pdf_count = len(list_pdf_files())
    if not os.path.exists(RAG_DB_PATH):
        return {
            "source_dir": RAG_SOURCE_DIR,
            "database": RAG_DB_PATH,
            "pdf_files": pdf_count,
            "indexed_documents": 0,
            "indexed_chunks": 0,
            "embedding_model": GEMINI_EMBEDDING_MODEL,
            "embedding_dim": GEMINI_EMBEDDING_DIM,
            "gemini_configured": bool(load_secret("GEMINI_API_KEY")),
        }

    with connect_rag_db() as conn:
        documents = conn.execute("SELECT COUNT(*) AS count FROM rag_documents").fetchone()["count"]
        chunks = conn.execute("SELECT COUNT(*) AS count FROM rag_chunks").fetchone()["count"]
        latest = conn.execute("SELECT MAX(indexed_at) AS indexed_at FROM rag_documents").fetchone()["indexed_at"]

    return {
        "source_dir": RAG_SOURCE_DIR,
        "database": RAG_DB_PATH,
        "pdf_files": pdf_count,
        "indexed_documents": documents,
        "indexed_chunks": chunks,
        "latest_indexed_at": latest,
        "embedding_model": GEMINI_EMBEDDING_MODEL,
        "embedding_dim": GEMINI_EMBEDDING_DIM,
        "gemini_configured": bool(load_secret("GEMINI_API_KEY")),
    }


def score_chunk(query_embedding, query_norm, row):
    if row["embedding_norm"] == 0:
        return 0.0

    embedding = unpack_embedding(row["embedding"])
    dim = min(len(query_embedding), len(embedding))
    dot = sum(float(query_embedding[index]) * float(embedding[index]) for index in range(dim))
    return dot / (query_norm * float(row["embedding_norm"]))


def search_rag(query, *, top_k=6, min_score=None):
    query = normalize_text(query)
    if not query:
        raise RuntimeError("Search query is empty.")

    query_embedding = gemini_embed_texts([query], task_type="RETRIEVAL_QUERY")[0]
    query_norm = vector_norm(query_embedding)
    if query_norm == 0:
        raise RuntimeError("Gemini returned a zero-length query embedding.")

    with connect_rag_db() as conn:
        rows = conn.execute(
            """
            SELECT
                c.id, c.chunk_index, c.page_number, c.text, c.embedding,
                c.embedding_norm, d.filename, d.source_path
            FROM rag_chunks c
            JOIN rag_documents d ON d.id = c.document_id
            WHERE c.embedding_model = ?
              AND c.embedding_dim = ?
            """,
            (GEMINI_EMBEDDING_MODEL, GEMINI_EMBEDDING_DIM),
        ).fetchall()

    scored = []
    for row in rows:
        score = score_chunk(query_embedding, query_norm, row)
        if min_score is not None and score < min_score:
            continue
        scored.append((score, row))

    scored.sort(key=lambda item: item[0], reverse=True)
    results = []
    for rank, (score, row) in enumerate(scored[:int(top_k)], start=1):
        text = row["text"]
        results.append({
            "rank": rank,
            "score": round(float(score), 4),
            "filename": row["filename"],
            "source_path": row["source_path"],
            "page": row["page_number"],
            "chunk": row["chunk_index"],
            "citation": f"{row['filename']}, p. {row['page_number']}",
            "passage": text,
            "snippet": text[:900].rstrip() + ("..." if len(text) > 900 else ""),
        })

    return {
        "query": query,
        "top_k": int(top_k),
        "results": results,
        "indexed_chunks_searched": len(rows),
        "embedding_model": GEMINI_EMBEDDING_MODEL,
    }


def build_clinical_context(query, *, top_k=6, max_passage_chars=1400):
    result = search_rag(query, top_k=top_k)
    lines = []
    for item in result["results"]:
        passage = item["passage"][:max_passage_chars].strip()
        if len(item["passage"]) > max_passage_chars:
            passage += "..."
        lines.append(
            f"[{item['rank']}] {item['citation']} | score {item['score']}\n{passage}"
        )
    return {
        "query": result["query"],
        "context": "\n\n".join(lines),
        "sources": [
            {
                "rank": item["rank"],
                "citation": item["citation"],
                "source_path": item["source_path"],
                "score": item["score"],
            }
            for item in result["results"]
        ],
    }


def print_json(data):
    print(json.dumps(data, ensure_ascii=False, indent=2))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Index and search local clinical RAG PDFs.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    index_parser = subparsers.add_parser("index", help="Extract, chunk, embed, and store PDF content.")
    index_parser.add_argument("--force", action="store_true", help="Re-index unchanged PDFs.")
    index_parser.add_argument("--limit", type=int, help="Index only the first N PDFs.")

    search_parser = subparsers.add_parser("search", help="Search the indexed books.")
    search_parser.add_argument("query", help="Clinical search query.")
    search_parser.add_argument("--top-k", type=int, default=6)

    subparsers.add_parser("status", help="Show local RAG index status.")

    args = parser.parse_args(argv)
    if args.command == "index":
        print_json(index_rag_files(force=args.force, limit=args.limit))
    elif args.command == "search":
        print_json(search_rag(args.query, top_k=args.top_k))
    elif args.command == "status":
        print_json(rag_status())


if __name__ == "__main__":
    main(sys.argv[1:])
