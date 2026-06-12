from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.policy_engine import PolicyLibrary
from app.receipt_reader import parse_receipt
from app.reviewer import review_line_item

try:
    from pypdf import PdfReader
except Exception as exc:  # pragma: no cover
    raise SystemExit(f"pypdf is required: {exc}")


def read_pdf(path: Path) -> str:
    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def evaluate(expected_path: Path) -> dict:
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    policies = PolicyLibrary(ROOT / "data" / "policies")
    total_expected = 0
    matched = 0
    citation_supported = 0
    reviewed_items = 0

    for case in expected:
        folder = ROOT / "data" / "seed_submissions" / case["folder"]
        employee = json.loads((folder / "employee_info.json").read_text(encoding="utf-8"))
        expected_keywords = [k.lower() for k in case.get("expected_flagged_keywords", [])]
        total_expected += len(expected_keywords)
        case_findings = []

        for receipt_file in sorted((folder / "receipts").glob("*.pdf")):
            text = read_pdf(receipt_file)
            receipt = parse_receipt(text, receipt_file.name)
            review = review_line_item(receipt, employee, policies)
            reviewed_items += 1
            if review["policy_quotes"]:
                citation_supported += 1
            if review["verdict"] != "Compliant":
                case_findings.append((receipt_file.name + " " + review["reasoning"]).lower())

        combined = " ".join(case_findings)
        for keyword in expected_keywords:
            if keyword in combined:
                matched += 1

    qa_refusal = policies.answer_question("Who won the Super Bowl?")["confidence"] == 0
    return {
        "expected_flag_recall": round(matched / total_expected, 3) if total_expected else 0,
        "citation_coverage": round(citation_supported / reviewed_items, 3) if reviewed_items else 0,
        "out_of_scope_refusal_passed": qa_refusal,
        "reviewed_items": reviewed_items,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(evaluate(args.expected), indent=2))
