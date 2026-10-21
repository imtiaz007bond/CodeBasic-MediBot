"""Docling HybridChunker ingestion with heading paths and safe fallback parsing."""
import re, hashlib, json
from pathlib import Path
from .config import DATA_DIR, COLLECTION_ACCESS

COLLECTION_FILES = {
    "general": ["staff_handbook.pdf", "leave_policy.pdf", "code_of_conduct.pdf", "general_faqs.pdf"],
    "clinical": ["treatment_protocols.pdf", "drug_formulary.pdf", "diagnostic_reference.pdf"],
    "nursing": ["icu_nursing_procedures.pdf", "infection_control.pdf"],
    "billing": ["billing_codes.pdf", "claim_submission_guide.md"],
    "equipment": ["equipment_manual.pdf"],
}


def _markdown_items(text: str):
    """Fallback chunker that retains the full Markdown heading path."""
    chunks, headings, body = [], [], []
    def flush():
        content = "\n".join(body).strip()
        if content:
            chunks.append((" › ".join(headings) or "Introduction", content,
                           "table" if "|" in content and "\n" in content else "text"))
        body.clear()
    for line in text.splitlines():
        stripped = line.strip()
        match = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if match:
            flush()
            level, heading = len(match.group(1)), match.group(2).strip()
            headings[:] = headings[:level-1]
            headings.append(heading)
        else:
            body.append(line)
            if len("\n".join(body)) >= 1800:
                flush()
    flush()
    return chunks


def _docling_items(path: Path):
    try:
        from docling.document_converter import DocumentConverter
        from docling.chunking import HybridChunker
        document = DocumentConverter().convert(str(path)).document
        chunker = HybridChunker()
        output = []
        for chunk in chunker.chunk(document):
            text = (getattr(chunk, "text", "") or "").strip()
            if not text:
                continue
            meta = getattr(chunk, "meta", None)
            headings = getattr(meta, "headings", None) or []
            section = " › ".join(str(h) for h in headings if h) or "Introduction"
            items = getattr(meta, "doc_items", None) or []
            item_types = {type(item).__name__.lower() for item in items}
            kind = "table" if any("table" in name for name in item_types) else "text"
            output.append((section, text, kind))
        if output:
            return output
        raise ValueError(f"Docling HybridChunker produced no chunks for {path.name}")
    except Exception as exc:
        # Explicit fallback keeps local setup usable when Docling cannot parse a file.
        if path.suffix.lower() == ".pdf":
            import fitz
            with fitz.open(path) as pdf:
                extracted = "\n\n".join(page.get_text("text") for page in pdf)
        else:
            extracted = path.read_text(encoding="utf-8", errors="ignore")
        chunks = _markdown_items(extracted)
        if not chunks:
            raise RuntimeError(f"Could not extract any text from {path}: {exc}") from exc
        return chunks


def load_chunks(data_dir: Path | None = None):
    data_dir = Path(data_dir or DATA_DIR).resolve()
    if not data_dir.is_dir():
        raise FileNotFoundError(f"Document data directory does not exist: {data_dir}. Set DATA_DIR to the medibot/data directory.")
    all_chunks, missing = [], []
    for collection, filenames in COLLECTION_FILES.items():
        for filename in filenames:
            path = data_dir / filename
            if not path.is_file():
                missing.append(filename)
                continue
            for i, (section, body, typ) in enumerate(_docling_items(path)):
                text = f"Section: {section}\nSource: {filename}\n\n{body}"
                all_chunks.append({
                    "id": hashlib.sha1(f"{filename}:{i}:{body}".encode()).hexdigest(),
                    "text": text,
                    "payload": {
                        "source_document": filename,
                        "collection": collection,
                        "access_roles": COLLECTION_ACCESS[collection],
                        "section_title": section,
                        "chunk_type": typ,
                    },
                })
    if not all_chunks:
        expected = ", ".join(name for names in COLLECTION_FILES.values() for name in names)
        raise RuntimeError(f"No document chunks were found in {data_dir}. Expected files include: {expected}. Check DATA_DIR and mounted files.")
    if missing:
        print(f"Warning: {len(missing)} expected source files are missing from {data_dir}: {', '.join(missing)}")
    print(f"Prepared {len(all_chunks)} chunks from {data_dir}")
    return all_chunks


if __name__ == "__main__":
    chunks = load_chunks()
    out = Path(__file__).resolve().parents[1] / "chunks_preview.json"
    out.write_text(json.dumps(chunks, indent=2, ensure_ascii=False))
    print(f"Created {len(chunks)} chunks -> {out}")
