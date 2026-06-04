"""Extraction de texte depuis PDF / Word / texte (suffisant pour les CV)."""
from pathlib import Path


def parse_file(path: str | Path) -> str:
    path = Path(path)
    ext = path.suffix.lower()
    if ext == ".pdf":
        return _pdf(path)
    if ext in (".docx", ".doc"):
        return _docx(path)
    if ext in (".txt", ".md"):
        return path.read_text(encoding="utf-8", errors="ignore")
    raise ValueError(f"Format non pris en charge : {ext}")


def _pdf(path: Path) -> str:
    import fitz
    with fitz.open(path) as doc:
        txt = "\n".join(page.get_text() for page in doc)
    if txt.strip():
        return txt
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        return "\n".join((p.extract_text() or "") for p in pdf.pages)


def _docx(path: Path) -> str:
    import docx
    return "\n".join(p.text for p in docx.Document(path).paragraphs)
