import requests
import json

# ── Test 1: Main analyze endpoint ──────────────────────────────────────────
print("=" * 60)
print("TEST 1: POST /analyze — chest pain, Pune, age 55, diabetes")
print("=" * 60)
r = requests.post(
    "http://localhost:8000/analyze",
    json={
        "query": "chest pain while walking",
        "location": "Pune",
        "age": 55,
        "conditions": ["diabetes"],
    },
    timeout=60,
)
print(f"HTTP Status: {r.status_code}")
d = r.json()
print(f"Condition       : {d.get('condition')}")
print(f"Procedure       : {d.get('procedure')}")
print(f"Specialty       : {d.get('specialty')}")
print(f"Urgency         : {d.get('urgency')}")
print(f"Hospitals found : {len(d.get('hospitals', []))}")
cost = d.get("cost_estimation", {})
total = cost.get("total_estimated_cost", {})
print(f"Cost range      : INR {total.get('min'):,} - {total.get('max'):,}")
print(f"City tier       : {cost.get('city_tier')}")
conf = d.get("confidence_score", {})
print(f"Confidence      : {conf.get('score')} ({conf.get('label')})")
print(f"Insights        : {len(d.get('insights', []))} items")
print("\nInsights:")
for i, ins in enumerate(d.get("insights", []), 1):
    print(f"  {i}. {ins}")
print("\nAlternatives:")
for a in d.get("alternatives", []):
    print(f"  - {a['condition']} (score: {a['score']})")
print("\nHospitals:")
for h in d.get("hospitals", []):
    print(f"  - {h['name']} | {h.get('distance_km')} km | score: {h.get('relevance_score')}")
    print(f"    Why: {h.get('why_recommended')}")
print("\nCost Breakdown:")
breakdown = cost.get("breakdown", {})
for k, v in breakdown.items():
    print(f"  {k}: {v}")
print(f"\nDisclaimer: {d.get('disclaimer')}")

# ── Test 2: Different query ─────────────────────────────────────────────────
print("\n" + "=" * 60)
print("TEST 2: POST /analyze — severe headache, Mumbai, age 35")
print("=" * 60)
r2 = requests.post(
    "http://localhost:8000/analyze",
    json={
        "query": "sudden severe headache and vomiting",
        "location": "Mumbai",
        "age": 35,
        "conditions": [],
    },
    timeout=60,
)
print(f"HTTP Status: {r2.status_code}")
d2 = r2.json()
print(f"Condition : {d2.get('condition')}")
print(f"Procedure : {d2.get('procedure')}")
print(f"Urgency   : {d2.get('urgency')}")
cost2 = d2.get("cost_estimation", {}).get("total_estimated_cost", {})
print(f"Cost      : INR {cost2.get('min'):,} - {cost2.get('max'):,}")
print(f"Confidence: {d2.get('confidence_score', {}).get('score')}")

# ── Test 3: Validation error ────────────────────────────────────────────────
print("\n" + "=" * 60)
print("TEST 3: POST /analyze — invalid input (empty query)")
print("=" * 60)
r3 = requests.post(
    "http://localhost:8000/analyze",
    json={"query": "", "location": "Delhi", "age": 30, "conditions": []},
    timeout=10,
)
print(f"HTTP Status: {r3.status_code} (expected 422)")
print(f"Error: {r3.json()}")

# ── Test 4: Reference endpoints ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("TEST 4: GET /procedures")
print("=" * 60)
r4 = requests.get("http://localhost:8000/procedures", timeout=10)
d4 = r4.json()
print(f"Total procedures: {d4['count']}")
print(f"Sample: {d4['procedures'][:5]}")

print("\n" + "=" * 60)
print("ALL TESTS COMPLETE")
print("=" * 60)
