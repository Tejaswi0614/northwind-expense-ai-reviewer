from __future__ import annotations

import re
import tempfile
from pathlib import Path
from typing import BinaryIO

from PIL import Image
from pypdf import PdfReader

try:
    import pytesseract
except Exception:  # pragma: no cover
    pytesseract = None


def _read_pdf(path: Path) -> str:
    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _read_image(path: Path) -> str:
    if pytesseract is None:
        return "OCR is not installed. Please install Tesseract to read image receipts."
    return pytesseract.image_to_string(Image.open(path))


def extract_text(uploaded_file: BinaryIO, filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp:
        temp.write(uploaded_file.read())
        temp_path = Path(temp.name)
    try:
        if suffix == ".pdf":
            return _read_pdf(temp_path)
        if suffix in {".txt", ".csv"}:
            return temp_path.read_text(encoding="utf-8", errors="ignore")
        if suffix in {".jpg", ".jpeg", ".png", ".webp"}:
            return _read_image(temp_path)
        return "Unsupported receipt type. Please upload PDF, JPG, PNG, WEBP, TXT, or CSV."
    finally:
        temp_path.unlink(missing_ok=True)


def parse_receipt(text: str, filename: str) -> dict:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    vendor = lines[0].replace("=", "").strip() if lines else Path(filename).stem
    money_values = [float(v.replace(",", "")) for v in re.findall(r"\$\s*([0-9][0-9,]*(?:\.\d{2})?)", text)]
    amount = max(money_values) if money_values else 0.0
    lowered = text.lower()

    if any(w in lowered for w in ["airlines", "flight", "e-ticket", "delta", "united", "american", "southwest", "alaska"]):
        category = "Air Travel"
    elif any(w in lowered for w in ["hotel", "marriott", "hyatt", "hilton", "lodging", "check-in", "check-out"]):
        category = "Lodging"
    elif any(w in lowered for w in ["uber", "lyft", "taxi", "ride receipt"]):
        category = "Ground Transportation"
    elif any(w in lowered for w in ["conference", "registration"]):
        category = "Conference"
    elif any(w in lowered for w in ["breakfast", "lunch", "dinner", "restaurant", "cafe", "menu", "coffee"]):
        category = "Meals"
    else:
        category = "General Expense"

    return {"vendor": vendor[:80], "amount": amount, "category": category, "text": text}
