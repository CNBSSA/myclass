import io
import re
from pathlib import Path

import pypdf
import nbformat
import pandas as pd

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
TEXT_EXTS = {".md", ".txt"}
PDF_EXTS = {".pdf"}
NOTEBOOK_EXTS = {".ipynb"}
CSV_EXTS = {".csv"}
EXCEL_EXTS = {".xlsx", ".xls"}

ALL_SUPPORTED_EXTS = (
    IMAGE_EXTS | TEXT_EXTS | PDF_EXTS | NOTEBOOK_EXTS | CSV_EXTS | EXCEL_EXTS
)


def _safe_filename(name: str) -> str:
    base = Path(name).name
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", base)
    return cleaned or "upload"


def _classify_ext(ext: str) -> str:
    ext = ext.lower()
    if ext in IMAGE_EXTS:    return "image"
    if ext in PDF_EXTS:      return "pdf"
    if ext in NOTEBOOK_EXTS: return "ipynb"
    if ext in CSV_EXTS:      return "csv"
    if ext in EXCEL_EXTS:    return "xlsx"
    if ext in TEXT_EXTS:     return "text"
    return "unknown"


def _extract_pdf(path: Path) -> str:
    reader = pypdf.PdfReader(str(path))
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as e:
            text = f"[Error extracting page {i}: {e}]"
        pages.append(f"--- Page {i} ---\n{text.strip()}")
    return "\n\n".join(pages)


def _extract_notebook(path: Path) -> str:
    nb = nbformat.read(str(path), as_version=4)
    parts = []
    for idx, cell in enumerate(nb.cells, start=1):
        if cell.cell_type == "markdown":
            parts.append(f"--- Cell {idx} (markdown) ---\n{cell.source}")
        elif cell.cell_type == "code":
            parts.append(f"--- Cell {idx} (code) ---\n```python\n{cell.source}\n```")
            for out in cell.get("outputs", []):
                if out.get("output_type") == "stream":
                    parts.append(f"[output]\n{out.get('text', '')}")
                elif out.get("output_type") in ("execute_result", "display_data"):
                    data = out.get("data", {})
                    if "text/plain" in data:
                        parts.append(f"[output]\n{data['text/plain']}")
    return "\n\n".join(parts)


def _extract_csv(path: Path, max_rows: int = 50) -> str:
    df = pd.read_csv(path)
    head = df.head(max_rows)
    return (
        f"CSV file: {path.name}\n"
        f"Shape: {df.shape[0]} rows x {df.shape[1]} columns\n"
        f"Columns: {list(df.columns)}\n"
        f"Dtypes:\n{df.dtypes.to_string()}\n\n"
        f"First {min(max_rows, len(df))} rows:\n{head.to_string()}\n"
    )


def _extract_excel(path: Path, max_rows: int = 50) -> str:
    xls = pd.ExcelFile(path)
    parts = [f"Excel file: {path.name}\nSheets: {xls.sheet_names}"]
    for sheet in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name=sheet)
        head = df.head(max_rows)
        parts.append(
            f"\n--- Sheet: {sheet} ---\n"
            f"Shape: {df.shape[0]} rows x {df.shape[1]} columns\n"
            f"Columns: {list(df.columns)}\n"
            f"First {min(max_rows, len(df))} rows:\n{head.to_string()}"
        )
    return "\n".join(parts)


def _extract_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def save_and_parse(filename: str, file_bytes: bytes, dest_dir: Path) -> dict:
    dest_dir.mkdir(parents=True, exist_ok=True)
    safe_name = _safe_filename(filename)
    saved_path = dest_dir / safe_name

    counter = 1
    while saved_path.exists():
        stem, suffix = Path(safe_name).stem, Path(safe_name).suffix
        saved_path = dest_dir / f"{stem}_{counter}{suffix}"
        counter += 1

    saved_path.write_bytes(file_bytes)
    ext = saved_path.suffix.lower()
    file_type = _classify_ext(ext)

    extracted_text: str | None = None
    try:
        if file_type == "pdf":     extracted_text = _extract_pdf(saved_path)
        elif file_type == "ipynb": extracted_text = _extract_notebook(saved_path)
        elif file_type == "csv":   extracted_text = _extract_csv(saved_path)
        elif file_type == "xlsx":  extracted_text = _extract_excel(saved_path)
        elif file_type == "text":  extracted_text = _extract_text(saved_path)
    except Exception as e:
        extracted_text = f"[Error parsing {filename}: {e}]"

    return {
        "filename": filename,
        "file_path": str(saved_path),
        "file_type": file_type,
        "extracted_text": extracted_text,
    }


def aggregate_text(files: list[dict]) -> str:
    sections = []
    for f in files:
        header = f"=== {f['filename']} ({f['file_type']}) ==="
        if f["file_type"] == "image":
            sections.append(f"{header}\n[Image content — see attached image]")
        elif f.get("extracted_text"):
            sections.append(f"{header}\n{f['extracted_text']}")
        else:
            sections.append(f"{header}\n[No extractable text]")
    return "\n\n".join(sections)


def image_paths(files: list[dict]) -> list[str]:
    return [f["file_path"] for f in files if f["file_type"] == "image"]
