from __future__ import annotations

import re
from app.policy_engine import PolicyLibrary

TIER_1_CITIES = {"boston", "chicago", "denver", "new york", "san francisco", "seattle", "washington"}
BASE_MEAL_CAPS = {"breakfast": 25.0, "lunch": 40.0, "dinner": 75.0}
LODGING_CAPS = {"tier1": 350.0, "default": 250.0}


def _trip_city(text: str, employee: dict) -> str:
    combined = " ".join([text, employee.get("trip_purpose", ""), employee.get("raw_json", "")]).lower()
    for city in TIER_1_CITIES | {"austin", "los angeles"}:
        if city in combined:
            return city
    return ""


def _meal_type(text: str) -> str:
    lowered = text.lower()
    if "breakfast" in lowered or "coffee" in lowered:
        return "breakfast"
    if "lunch" in lowered:
        return "lunch"
    return "dinner"


def _contains_alcohol(text: str) -> bool:
    alcohol_words = ["beer", "wine", "cocktail", "whiskey", "vodka", "margarita", "alcohol", "bar"]
    return any(word in text.lower() for word in alcohol_words)


def _tip_percent(text: str) -> float | None:
    totals = [float(v) for v in re.findall(r"\$\s*([0-9]+(?:\.\d{2})?)", text)]
    tip_match = re.search(r"tip[^\$]{0,20}\$\s*([0-9]+(?:\.\d{2})?)", text, re.I)
    if not tip_match or len(totals) < 2:
        return None
    tip = float(tip_match.group(1))
    likely_subtotal = max(v for v in totals if v < max(totals))
    return round((tip / likely_subtotal) * 100, 1) if likely_subtotal else None


def review_line_item(receipt: dict, employee: dict, policies: PolicyLibrary) -> dict:
    category = receipt["category"]
    amount = float(receipt.get("amount") or 0)
    text = receipt.get("text", "")
    city = _trip_city(text, employee)
    verdict = "Compliant"
    reasons: list[str] = []
    query = category
    confidence = 0.72

    if amount <= 0:
        verdict = "Needs Human Review"
        reasons.append("The system could not extract a reliable amount from the receipt.")
        confidence = 0.35

    if category == "Meals":
        meal = _meal_type(text)
        cap = BASE_MEAL_CAPS[meal] * (1.25 if city in TIER_1_CITIES else 1.0)
        query = f"{meal} meal cap tip alcohol itemized receipt"
        if amount > cap:
            verdict = "Flagged"
            reasons.append(f"The {meal} total of ${amount:.2f} is above the estimated cap of ${cap:.2f}.")
        if _contains_alcohol(text) and ("client" not in text.lower() and "external" not in text.lower()):
            verdict = "Rejected"
            reasons.append("Alcohol appears on a solo/team-only travel receipt without client entertainment context.")
        tip = _tip_percent(text)
        if tip and tip > 20:
            verdict = "Flagged"
            reasons.append(f"Tip appears to be {tip}% of the pre-tax amount, above the 20% guideline.")

    elif category == "Lodging":
        cap = LODGING_CAPS["tier1"] if city in TIER_1_CITIES else LODGING_CAPS["default"]
        query = "lodging hotel nightly cap tier city reimbursable"
        if amount > cap:
            verdict = "Flagged"
            reasons.append(f"Hotel charge of ${amount:.2f} may exceed the nightly lodging cap of ${cap:.2f}.")

    elif category == "Air Travel":
        query = "air travel economy first class booking advance approval"
        if "first class" in text.lower():
            verdict = "Rejected"
            reasons.append("First class air travel is not reimbursable.")
        elif any(term in text.lower() for term in ["business class", "premium economy"]):
            verdict = "Needs Human Review"
            reasons.append("Premium cabin travel needs duration/approval validation.")

    elif category == "Ground Transportation":
        query = "ground transportation rideshare taxi airport transfer reimbursable receipt"
        if any(term in text.lower() for term in ["xl", "lux", "black"]):
            verdict = "Needs Human Review"
            reasons.append("Premium rideshare class may require business justification.")

    elif category == "Conference":
        query = "conference attendance registration meals approval reimbursement"
        verdict = "Compliant"
        reasons.append("Conference registration is generally reviewable as a business expense when tied to trip purpose.")

    if not reasons:
        reasons.append("No obvious policy issue was detected from the extracted receipt text.")

    hits = policies.search(query, limit=3)
    quotes = [
        {"document": chunk.document, "quote": chunk.text[:650], "score": round(score, 3)}
        for chunk, score in hits
    ]
    if hits:
        confidence = min(0.95, confidence + hits[0][1] / 3)
    else:
        confidence = min(confidence, 0.45)
        reasons.append("Policy support was weak, so a reviewer should verify this item.")

    return {
        "verdict": verdict,
        "confidence": round(confidence, 2),
        "reasoning": " ".join(reasons),
        "policy_quotes": quotes,
    }
