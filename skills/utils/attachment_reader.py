"""
Attachment reader.

Supports:
  • PDF  – via pdfplumber (text + table extraction)
  • Excel / XLS / XLSX – via pandas
  • CSV  – via pandas
  • Plain text / other – direct UTF-8 decode
"""
from __future__ import annotations

import io
import os
from typing import Any

import pandas as pd
import pdfplumber

MAX_PDF_PAGES = int(os.getenv("MAX_PDF_PAGES", "50"))
MAX_EXCEL_ROWS = int(os.getenv("MAX_EXCEL_ROWS", "500"))


# ── PDF ──────────────────────────────────────────────────────────────────────

def _read_pdf(data: bytes) -> str:
    """Extract text (and simple tables) from a PDF byte-string."""
    pages_text: list[str] = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for i, page in enumerate(pdf.pages):
            if i >= MAX_PDF_PAGES:
                pages_text.append(
                    f"[Truncated – showing first {MAX_PDF_PAGES} pages only]"
                )
                break
            text = page.extract_text() or ""
            # Also pull tables
            tables = page.extract_tables()
            table_text = ""
            for tbl in tables:
                for row in tbl:
                    table_text += " | ".join(str(c or "") for c in row) + "\n"
            combined = (text + "\n" + table_text).strip()
            if combined:
                pages_text.append(f"--- Page {i + 1} ---\n{combined}")
    return "\n\n".join(pages_text) if pages_text else "[No extractable text in PDF]"


# ── Excel / CSV ──────────────────────────────────────────────────────────────

def _read_excel(data: bytes, mime_type: str) -> str:
    """Read an Excel/CSV file and return a markdown-ish table string."""
    buf = io.BytesIO(data)
    try:
        if mime_type == "text/csv" or mime_type.endswith("csv"):
            df = pd.read_csv(buf, nrows=MAX_EXCEL_ROWS)
        else:
            df = pd.read_excel(buf, nrows=MAX_EXCEL_ROWS)
    except Exception as exc:
        return f"[Could not parse file: {exc}]"

    rows, cols = df.shape
    header = " | ".join(str(c) for c in df.columns)
    sep = " | ".join(["---"] * cols)
    rows_text = "\n".join(
        " | ".join(str(v) for v in row) for row in df.values
    )
    truncation = (
        f"\n[Showing first {MAX_EXCEL_ROWS} rows of {rows} total]"
        if rows >= MAX_EXCEL_ROWS
        else ""
    )
    return f"{header}\n{sep}\n{rows_text}{truncation}"


# ── Public entrypoint ────────────────────────────────────────────────────────

def read_attachment(data: bytes, filename: str, mime_type: str = "") -> dict[str, Any]:
    """
    Parse attachment bytes and return:
        {
            "filename": str,
            "mime_type": str,
            "content": str,   # extracted text
            "error": str | None
        }
    """
    fname_lower = filename.lower()
    mime_lower = mime_type.lower()

    content = ""
    error = None

    try:
        if fname_lower.endswith(".pdf") or "pdf" in mime_lower:
            content = _read_pdf(data)

        elif any(fname_lower.endswith(ext) for ext in (".xls", ".xlsx", ".xlsm", ".xlsb")):
            content = _read_excel(data, mime_lower)

        elif fname_lower.endswith(".csv") or "csv" in mime_lower:
            content = _read_excel(data, "text/csv")

        elif any(fname_lower.endswith(ext) for ext in (".txt", ".md", ".log", ".json", ".xml")):
            content = data.decode("utf-8", errors="replace")

        else:
            # Attempt plain-text decode as fallback
            try:
                content = data.decode("utf-8", errors="strict")
            except Exception:
                content = f"[Binary attachment – {len(data):,} bytes, cannot display as text]"

    except Exception as exc:
        error = str(exc)
        content = f"[Error reading attachment: {exc}]"

    return {
        "filename": filename,
        "mime_type": mime_type,
        "content": content,
        "error": error,
    }
