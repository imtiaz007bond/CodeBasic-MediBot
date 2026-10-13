"""Docling-first structural ingestion with section-aware fallback parsing."""
import re, hashlib, json, os
from pathlib import Path
from typing import Iterable
from .config import DATA_DIR, COLLECTION_ACCESS

COLLECTION_FILES = {
 "general": ["staff_handbook.pdf", "leave_policy.pdf", "code_of_conduct.pdf", "general_faqs.pdf"],
 "clinical": ["treatment_protocols.pdf", "drug_formulary.pdf", "diagnostic_reference.pdf"],
 "nursing": ["icu_nursing_procedures.pdf", "infection_control.pdf"],
 "billing": ["billing_codes.pdf", "claim_submission_guide.md"],
 "equipment": ["equipment_manual.pdf"],
}

def _docling_items(path: Path):
    try:
        from docling.document_converter import DocumentConverter
        from docling_core.types.doc import DoclingDocument
        doc = DocumentConverter().convert(str(path)).document
        # Export markdown preserves headings and tables as markdown.
        md = doc.export_to_markdown()
        return _markdown_items(md)
    except Exception:
        if path.suffix.lower() == ".pdf":
            import fitz
            d = fitz.open(path)
            return _markdown_items("\n\n".join(p.get_text("text") for p in d))
        return _markdown_items(path.read_text(encoding="utf-8", errors="ignore"))

def _markdown_items(text: str):
    items, section, buf = [], "Introduction", []
    def flush():
        body = "\n".join(buf).strip()
        if body: items.append((section, body, "table" if "|" in body and "\n" in body else "text"))
        buf.clear()
    for line in text.splitlines():
        s=line.strip()
        if not s: 
            if buf: buf.append("")
            continue
        heading = re.match(r"^(#{1,6})\s+(.+)$", s) or re.match(r"^([A-Z][A-Z0-9 /&(),:'-]{5,})$", s)
        if heading:
            flush(); section = heading.group(2).strip() if heading.lastindex and heading.lastindex >= 2 else s
            items.append((section, section, "heading")); continue
        buf.append(line)
    flush()
    # Second pass: bounded paragraph-aware chunks; never split markdown table rows from headers when possible.
    chunks=[]
    for section, body, typ in items:
        if typ == "heading": continue
        paras = re.split(r"\n\s*\n", body)
        current=""
        for para in paras:
            para=para.strip()
            if not para: continue
            if len(current)+len(para)>1800 and current:
                chunks.append((section,current,typ)); current=""
            current = (current+"\n\n"+para).strip()
        if current: chunks.append((section,current,typ))
    return chunks

def load_chunks(data_dir: Path = DATA_DIR):
    all_chunks=[]
    for collection, files in COLLECTION_FILES.items():
        for filename in files:
            path=data_dir/filename
            if not path.exists(): continue
            for i,(section,body,typ) in enumerate(_docling_items(path)):
                text=f"Section: {section}\nSource: {filename}\n\n{body}"
                all_chunks.append({"id": hashlib.sha1(f"{filename}:{i}:{body}".encode()).hexdigest(), "text":text,
                    "payload":{"source_document":filename,"collection":collection,"access_roles":COLLECTION_ACCESS[collection],"section_title":section,"chunk_type":typ}})
    return all_chunks

if __name__ == "__main__":
    chunks=load_chunks()
    out=Path(__file__).resolve().parents[1]/"chunks_preview.json"
    out.write_text(json.dumps(chunks,indent=2,ensure_ascii=False))
    print(f"Created {len(chunks)} chunks -> {out}")
