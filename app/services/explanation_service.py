import logging

logger = logging.getLogger(__name__)

URGENCY_ADVICE = {
    "Emergency": "⚠️ URGENT: Seek emergency care immediately. Do not delay.",
    "High": "This condition requires prompt medical attention within 24–48 hours.",
    "Medium": "Schedule a consultation within the next few days.",
    "Low": "This can be addressed at your next routine appointment.",
}


def build_insights(nlp_result: dict, cost_result: dict, hospitals: list[dict], age: int, conditions: list[str]) -> list[str]:
    insights = []

    urgency = nlp_result.get("urgency", "Medium")
    insights.append(URGENCY_ADVICE.get(urgency, "Consult a doctor at your earliest convenience."))

    insights.append(
        f"Based on your symptoms ('{nlp_result['matched_symptom']}'), the most likely condition is "
        f"**{nlp_result['condition']}**, which typically requires **{nlp_result['procedure']}** "
        f"under {nlp_result['specialty']} specialty."
    )

    if age >= 60:
        insights.append("Patients above 60 often face higher procedural complexity and longer recovery times — costs are adjusted accordingly.")
    elif age >= 40:
        insights.append("Middle-aged patients may have underlying risk factors; a thorough pre-procedure evaluation is recommended.")

    if conditions:
        insights.append(
            f"Comorbidities ({', '.join(conditions)}) increase procedural risk and cost. "
            "Ensure your treating physician is aware of all existing conditions."
        )

    if hospitals:
        top = hospitals[0]
        insights.append(
            f"Top recommended hospital: **{top['name']}** — {top['distance_km']} km away "
            f"(relevance score: {top['relevance_score']})."
        )

    if "total_estimated_cost" in cost_result:
        display = cost_result["total_estimated_cost"]["display"]
        tier = cost_result.get("city_tier", "")
        insights.append(f"Estimated total cost in a {tier} facility: {display} (includes procedure, stay, medicines & 10% contingency).")

    alts = nlp_result.get("alternatives", [])
    if alts:
        alt_names = [a["condition"] for a in alts[:2]]
        insights.append(f"Differential diagnoses to rule out: {', '.join(alt_names)}.")

    return insights


def build_hospital_explanations(hospitals: list[dict], specialty: str) -> list[dict]:
    explained = []
    for h in hospitals:
        reasons = []
        if h["distance_km"] <= 2:
            reasons.append(f"Very close — only {h['distance_km']} km away")
        elif h["distance_km"] <= 5:
            reasons.append(f"Nearby — {h['distance_km']} km away")
        else:
            reasons.append(f"{h['distance_km']} km from your location")

        if specialty.lower() in h.get("speciality", "").lower():
            reasons.append(f"Specialises in {specialty}")
        if h.get("emergency") in ("yes", "24/7"):
            reasons.append("Has 24/7 emergency services")
        if h.get("beds") not in ("N/A", None, ""):
            reasons.append(f"Capacity: {h['beds']} beds")

        explained.append({**h, "why_recommended": "; ".join(reasons) if reasons else "Listed hospital in your area"})
    return explained


def calculate_confidence(nlp_score: float, hospital_count: int, cost_found: bool) -> dict:
    nlp_weight = nlp_score * 0.50
    hospital_weight = min(hospital_count / 5, 1.0) * 0.30
    cost_weight = 0.20 if cost_found else 0.0
    total = round(nlp_weight + hospital_weight + cost_weight, 4)

    if total >= 0.75:
        label = "High"
        note = "Strong match across symptoms, hospital data, and cost estimation."
    elif total >= 0.50:
        label = "Medium"
        note = "Reasonable match; some data sources had limited results."
    else:
        label = "Low"
        note = "Limited data available; results should be verified with a medical professional."

    return {
        "score": total,
        "label": label,
        "note": note,
        "components": {
            "nlp_similarity": round(nlp_weight, 4),
            "hospital_data_quality": round(hospital_weight, 4),
            "cost_data_availability": round(cost_weight, 4),
        },
    }
