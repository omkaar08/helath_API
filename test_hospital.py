from app.services.hospital_service import get_hospitals

result = get_hospitals("Pune", "Cardiology", limit=5)
print("Total found:", result["total_found"])
print("Source:", result["source"])
if result.get("error"):
    print("Error:", result["error"])
for h in result["hospitals"]:
    print(f"  - {h['name']} | {h['distance_km']} km | score: {h['relevance_score']}")
    print(f"    Address : {h['address']}")
    print(f"    Emergency: {h['emergency']} | Type: {h['type']}")
