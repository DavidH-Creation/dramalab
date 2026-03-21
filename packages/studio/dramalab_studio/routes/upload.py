"""File upload endpoint."""

from __future__ import annotations

import io

from fastapi import APIRouter, File, HTTPException, UploadFile

router = APIRouter()

_ALLOWED_EXTENSIONS = {".docx", ".md", ".txt"}


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload a file and extract text content."""
    filename = file.filename or "unknown"
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type: {ext}. Allowed: {_ALLOWED_EXTENSIONS}")

    content = await file.read()

    if ext == ".docx":
        from docx import Document
        doc = Document(io.BytesIO(content))
        text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    else:
        text = content.decode("utf-8")

    return {
        "text": text,
        "filename": filename,
        "size_kb": round(len(content) / 1024, 1),
    }
