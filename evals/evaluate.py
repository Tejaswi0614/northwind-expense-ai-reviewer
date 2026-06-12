from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.policy_engine import PolicyLibrary
from app.receipt_reader import parse_receipt
from app.reviewer import review_line_item

POLICY_DIR = ROOT / "data" / "policies"


def load_json(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def calculate_accuracy(expected: list[str], predicted: list[str]) -> float:
    if not expected:
        return 0.0

    correct = 0

    for exp, pred in zip(expected, predicted):
        if exp.lower().strip() == pred.lower().strip():
            correct += 1

    return round(correct / len(expected), 3)


def calculate_refusal_rate(results: list[dict[str, Any]]) -> float:
    if not results:
        return 0.0

    refused = 0

    for result in results:
        if result.get("verdict") == "Needs Human Review":
            refused += 1

    return round(refused / len(results), 3)


def citation_quality(results: list[dict[str, Any]]) -> float:
    if not results:
        return 0.0

    supported = 0

    for result in results:
        quotes = result.get("policy_quotes", [])

        if quotes and any(q.get("quote") for q in quotes):
            supported += 1

    return round(supported / len(results), 3)


def evaluate_case(case: dict[str, Any], policies: PolicyLibrary) -> dict[str, Any]:
    receipt_text = case.get("receipt_text", "")
    filename = case.get("filename", "test_receipt.txt")
    employee = case.get("employee", {})

    receipt = parse_receipt(receipt_text, filename)
    review = review_line_item(receipt, employee, policies)

    return {
        "case_id": case.get("case_id"),
        "expected_verdict": case.get("expected_verdict"),
        "predicted_verdict": review.get("verdict"),
        "confidence": review.get("confidence"),
        "reasoning": review.get("reasoning"),
        "policy_quotes": review.get("policy_quotes", []),
    }


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python evals/evaluate.py evals/sample_expected.json")
        sys.exit(1)

    input_path = Path(sys.argv[1])

    if not input_path.exists():
        print(f"File not found: {input_path}")
        sys.exit(1)

    cases = load_json(input_path)
    policies = PolicyLibrary(POLICY_DIR)

    results = []

    for case in cases:
        results.append(evaluate_case(case, policies))

    expected = [r["expected_verdict"] for r in results]
    predicted = [r["predicted_verdict"] for r in results]

    report = {
        "total_cases": len(results),
        "verdict_accuracy": calculate_accuracy(expected, predicted),
        "citation_quality": citation_quality(results),
        "human_review_rate": calculate_refusal_rate(
            [{"verdict": r["predicted_verdict"]} for r in results]
        ),
        "results": results,
    }

    output_path = ROOT / "evals" / "evaluation_report.json"

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(report, file, indent=2)

    print(json.dumps(report, indent=2))
    print(f"\nEvaluation report saved to: {output_path}")


if __name__ == "__main__":
    main()