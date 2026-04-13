# AI Healthcare Navigator & Cost Estimator — India

A production-ready backend that combines **semantic NLP**, **real hospital data from OpenStreetMap**, and **evidence-based cost estimation** for Indian healthcare.

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start the server
python run.py

# 3. Open docs
http://localhost:8000/docs
```

---

## Architecture

```
POST /analyze
     │
     ├── NLP Service          sentence-transformers (all-MiniLM-L6-v2)
     │   └── query → condition + procedure + specialty + urgency
     │
     ├── Hospital Service     OpenStreetMap Overpass API (FREE, no key needed)
     │   └── location → geocode → fetch hospitals → score + rank
     │
     ├── Cost Service         CSV-backed with city tier × age × comorbidity multipliers
     │   └── procedure + city + age + conditions → cost range (INR)
     │
     ├── Explanation Service  Human-readable insights + hospital "why recommended"
     │
     └── Confidence Scorer    NLP score × hospital quality × cost data availability
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/analyze` | Main endpoint — full analysis |
| GET | `/health` | Health check |
| GET | `/procedures` | List all 54 supported procedures |
| GET | `/conditions` | List all 54 symptom→condition mappings |
| DELETE | `/cache` | Clear hospital cache |
| GET | `/docs` | Swagger UI |

---

## POST /analyze — Postman Guide

**URL:** `POST http://localhost:8000/analyze`  
**Headers:** `Content-Type: application/json`

**Request Body:**
```json
{
  "query": "chest pain while walking",
  "location": "Pune",
  "age": 55,
  "conditions": ["diabetes"]
}
```

**Sample Response:**
```json
{
  "condition": "Stable Angina",
  "procedure": "Stress Test + Angiography",
  "specialty": "Cardiology",
  "urgency": "High",
  "matched_symptom": "chest pain while walking",
  "hospitals": [
    {
      "name": "Ishwar Heart Clinic",
      "address": "403, Varun Capital, JM Road, Pune",
      "latitude": 18.519,
      "longitude": 73.856,
      "distance_km": 0.61,
      "relevance_score": 0.8634,
      "phone": "N/A",
      "type": "clinic",
      "emergency": "N/A",
      "why_recommended": "Very close — only 0.61 km away; Specialises in Cardiology"
    }
  ],
  "cost_estimation": {
    "procedure": "Stress Test + Angiography",
    "city": "Pune",
    "city_tier": "Tier 1 Metro",
    "breakdown": {
      "procedure_cost": { "min": 38639, "max": 86939 },
      "hospital_stay": { "days": "1–3", "cost": { "min": 3500, "max": 18900 } },
      "medicines": { "min": 8400, "max": 20160 },
      "contingency_10pct": { "min": 5053, "max": 12599 }
    },
    "total_estimated_cost": {
      "min": 55592,
      "max": 138598,
      "currency": "INR",
      "display": "₹55,592 – ₹138,598"
    },
    "adjustments_applied": {
      "city_multiplier": 1.4,
      "age_multiplier": 1.15,
      "comorbidity_multiplier": 1.2,
      "comorbidities_detected": ["diabetes"]
    }
  },
  "confidence_score": {
    "score": 1.0,
    "label": "High",
    "note": "Strong match across symptoms, hospital data, and cost estimation.",
    "components": {
      "nlp_similarity": 0.5,
      "hospital_data_quality": 0.3,
      "cost_data_availability": 0.2
    }
  },
  "insights": [
    "This condition requires prompt medical attention within 24–48 hours.",
    "Based on your symptoms ('chest pain while walking'), the most likely condition is Stable Angina...",
    "Top recommended hospital: Ishwar Heart Clinic — 0.61 km away (relevance score: 0.8634).",
    "Estimated total cost in a Tier 1 Metro facility: ₹55,592 – ₹138,598"
  ],
  "alternatives": [
    { "condition": "Angina / Coronary Artery Disease", "procedure": "Coronary Angiography", "score": 0.8017 }
  ],
  "disclaimer": "This system provides decision support only and is NOT a substitute for professional medical advice..."
}
```

---

## Sample Queries to Test

```json
{ "query": "sudden severe headache", "location": "Mumbai", "age": 35, "conditions": [] }
{ "query": "frequent urination and excessive thirst", "location": "Delhi", "age": 45, "conditions": ["obesity"] }
{ "query": "knee pain while climbing stairs", "location": "Bangalore", "age": 60, "conditions": ["diabetes", "hypertension"] }
{ "query": "persistent cough with fever", "location": "Chennai", "age": 30, "conditions": [] }
{ "query": "blood in urine", "location": "Hyderabad", "age": 50, "conditions": [] }
```

---

## Cost Formula

```
total = (base_cost × city_multiplier × age_multiplier × comorbidity_multiplier)
      + hospital_stay_cost
      + medicine_cost
      + 10% contingency
```

| Factor | Values |
|--------|--------|
| City Tier 1 (Mumbai, Delhi, Pune…) | ×1.4 |
| City Tier 2 (Jaipur, Lucknow…) | ×1.1 |
| City Tier 3 (small towns) | ×0.85 |
| Age < 40 | ×1.0 |
| Age 40–60 | ×1.15 |
| Age > 60 | ×1.30 |
| Diabetes comorbidity | +20% |
| Heart disease comorbidity | +25% |

---

## Caching

Hospital data is cached in `cache/` as JSON files (24-hour TTL).  
Clear cache: `DELETE http://localhost:8000/cache`

---

## Project Structure

```
health/
├── app/
│   ├── main.py                  # FastAPI app, routes, middleware
│   ├── models.py                # Pydantic request/response models
│   └── services/
│       ├── nlp_service.py       # sentence-transformers semantic matching
│       ├── hospital_service.py  # OpenStreetMap Overpass API + caching
│       ├── cost_service.py      # Cost estimation engine
│       └── explanation_service.py  # Insights + confidence scoring
├── data/
│   ├── medical_mapping.csv      # 54 symptom→condition→procedure mappings
│   ├── procedure_costs.csv      # 54 procedures with INR cost ranges
│   └── city_tiers.json          # Indian city tier multipliers
├── cache/                       # Auto-generated hospital cache (gitignore)
├── run.py                       # Entry point
├── test_api.py                  # Full test suite
└── requirements.txt
```
