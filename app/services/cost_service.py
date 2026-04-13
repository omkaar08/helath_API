import json
import logging
import pandas as pd
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent / "data"
_costs_df: pd.DataFrame | None = None
_city_tiers: dict | None = None

COMORBIDITY_RISK = {
    "diabetes": 0.20,
    "hypertension": 0.15,
    "heart disease": 0.25,
    "obesity": 0.15,
    "copd": 0.20,
    "kidney disease": 0.25,
    "liver disease": 0.20,
    "cancer": 0.30,
    "hiv": 0.20,
    "asthma": 0.10,
}


def _load():
    global _costs_df, _city_tiers
    if _costs_df is None:
        _costs_df = pd.read_csv(DATA_DIR / "procedure_costs.csv")
        _city_tiers = json.loads((DATA_DIR / "city_tiers.json").read_text())


def _get_city_multiplier(city: str) -> tuple[float, str]:
    _load()
    city_lower = city.lower().strip()
    for tier, info in _city_tiers.items():
        if city_lower in info["cities"]:
            return info["multiplier"], info["label"]
    return _city_tiers["tier3"]["multiplier"], _city_tiers["tier3"]["label"]


def _age_factor(age: int) -> float:
    if age < 18:
        return 0.85
    if age < 40:
        return 1.0
    if age < 60:
        return 1.15
    return 1.30


def _comorbidity_factor(conditions: list[str]) -> tuple[float, list[str]]:
    total = 0.0
    matched = []
    for c in conditions:
        for key, risk in COMORBIDITY_RISK.items():
            if key in c.lower():
                total += risk
                matched.append(key)
                break
    return round(1.0 + min(total, 0.60), 4), matched


def estimate_cost(procedure: str, city: str, age: int, conditions: list[str]) -> dict:
    _load()

    row = _costs_df[_costs_df["procedure"].str.lower() == procedure.lower()]
    if row.empty:
        # fuzzy fallback: partial match
        mask = _costs_df["procedure"].str.lower().str.contains(procedure.lower().split()[0], na=False)
        row = _costs_df[mask]

    if row.empty:
        return {"error": f"No cost data found for procedure: {procedure}"}

    row = row.iloc[0]
    city_mult, city_label = _get_city_multiplier(city)
    age_mult = _age_factor(age)
    comorbidity_mult, matched_conditions = _comorbidity_factor(conditions)

    total_mult = city_mult * age_mult * comorbidity_mult

    proc_min = int(row["base_cost_min"] * total_mult)
    proc_max = int(row["base_cost_max"] * total_mult)

    stay_cost_min = int(row["stay_days_min"] * 2500 * city_mult)
    stay_cost_max = int(row["stay_days_max"] * 4500 * city_mult)

    med_min = int(row["medicine_cost_min"] * city_mult * comorbidity_mult)
    med_max = int(row["medicine_cost_max"] * city_mult * comorbidity_mult)

    contingency_pct = 0.10
    grand_min = int((proc_min + stay_cost_min + med_min) * (1 + contingency_pct))
    grand_max = int((proc_max + stay_cost_max + med_max) * (1 + contingency_pct))

    return {
        "procedure": row["procedure"],
        "city": city,
        "city_tier": city_label,
        "breakdown": {
            "procedure_cost": {"min": proc_min, "max": proc_max},
            "hospital_stay": {
                "days": f"{int(row['stay_days_min'])}–{int(row['stay_days_max'])}",
                "cost": {"min": stay_cost_min, "max": stay_cost_max},
            },
            "medicines": {"min": med_min, "max": med_max},
            "contingency_10pct": {
                "min": int((proc_min + stay_cost_min + med_min) * contingency_pct),
                "max": int((proc_max + stay_cost_max + med_max) * contingency_pct),
            },
        },
        "total_estimated_cost": {
            "min": grand_min,
            "max": grand_max,
            "currency": "INR",
            "display": f"₹{grand_min:,} – ₹{grand_max:,}",
        },
        "adjustments_applied": {
            "city_multiplier": city_mult,
            "age_multiplier": age_mult,
            "comorbidity_multiplier": comorbidity_mult,
            "comorbidities_detected": matched_conditions,
        },
    }
