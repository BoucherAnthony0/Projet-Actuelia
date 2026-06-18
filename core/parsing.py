"""Extraction de texte depuis PDF / Word / texte et emails."""
from email import policy
from email.message import Message
from email.parser import BytesParser
from html import unescape
import json
from pathlib import Path
import re


_HTML_TAG_RE = re.compile(r"<[^>]+>")


def parse_file(path: str | Path) -> str:
    path = Path(path)
    ext = path.suffix.lower()
    if ext == ".pdf":
        return _pdf(path)
    if ext in (".docx", ".doc"):
        return _docx(path)
    if ext in (".txt", ".md"):
        return path.read_text(encoding="utf-8", errors="ignore")
    if ext == ".eml":
        return _eml(path)
    if ext == ".msg":
        return _msg(path)
    raise ValueError(f"Format non pris en charge : {ext}")


def parse_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def build_request_draft(raw_text: str, source_name: str | None = None) -> dict:
    texte = parse_text(raw_text)
    lignes = [line.strip() for line in texte.splitlines() if line.strip()]
    reference = _extract_reference(texte)
    titre = lignes[0] if lignes else ""
    livrables = _extract_livrables(lignes)
    return {
        "reference": reference,
        "titre": titre,
        "client_nom": _extract_client_name(texte),
        "source_name": source_name or "",
        "texte_brut": texte,
        "analyse_json": {
            "source": source_name or "texte collé",
            "resume": titre,
            "livrables": livrables,
        },
    }


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


def _eml(path: Path) -> str:
    message = BytesParser(policy=policy.default).parsebytes(path.read_bytes())
    text = _message_text(message)
    if text.strip():
        return text
    return message.as_string()


def _msg(path: Path) -> str:
    try:
        import extract_msg
    except ImportError as exc:
        raise RuntimeError("Le support .msg nécessite la dépendance extract-msg") from exc

    message = extract_msg.Message(str(path))
    try:
        text = message.body or message.htmlBody or ""
        if not text.strip():
            return ""
        if message.htmlBody and not message.body:
            return _strip_html(text)
        return text
    finally:
        message.close()


def _message_text(message: Message) -> str:
    if message.is_multipart():
        parts: list[str] = []
        html_parts: list[str] = []
        for part in message.iter_parts():
            if part.get_content_disposition() == "attachment":
                continue
            part_text = _message_text(part)
            if not part_text.strip():
                continue
            if part.get_content_type() == "text/html":
                html_parts.append(_strip_html(part_text))
            else:
                parts.append(part_text)
        if parts:
            return "\n".join(parts)
        if html_parts:
            return "\n".join(html_parts)
        return ""

    content = message.get_content()
    if isinstance(content, bytes):
        charset = message.get_content_charset() or "utf-8"
        content = content.decode(charset, errors="ignore")
    if message.get_content_type() == "text/html":
        return _strip_html(content)
    return content


def _strip_html(text: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", "", text)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p\s*>", "\n", text)
    text = _HTML_TAG_RE.sub(" ", text)
    text = unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    return "\n".join(line.strip() for line in text.splitlines()).strip()


def _extract_reference(text: str) -> str:
    match = re.search(r"\bRFX\d{4,}\b", text, flags=re.IGNORECASE)
    return match.group(0).upper() if match else ""


def _extract_client_name(text: str) -> str:
    patterns = (
        r"\bclient\s*[:\-]\s*(.+)",
        r"\bma\s*?\s*?client\s*[:\-]\s*(.+)",
        r"\bdonneur d['’]ordre\s*[:\-]\s*(.+)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip().splitlines()[0]
    return ""


def _extract_livrables(lines: list[str]) -> list[str]:
    livrables: list[str] = []
    for line in lines:
        if re.match(r"^([\-*•]|\d+[.)])\s+", line):
            livrables.append(re.sub(r"^([\-*•]|\d+[.)])\s+", "", line).strip())
        elif re.search(r"\blivrable\b", line, flags=re.IGNORECASE):
            cleaned = re.sub(r"^.*?livrables?\s*[:\-]\s*", "", line, flags=re.IGNORECASE).strip()
            if cleaned and cleaned not in livrables:
                livrables.append(cleaned)
    if not livrables and lines:
        livrables = lines[1:4]
    return livrables
