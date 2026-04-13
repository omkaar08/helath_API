import json
import logging
import math
import time
import hashlib
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).parent.parent.parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)
CACHE_TTL = 86400  # 24 hours

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]
HEADERS = {"User-Agent": "HealthcareNavigatorIndia/1.0 (educational project)"}


def _cache_key(location: str) -> Path:
    key = hashlib.md5(location.lower().encode()).hexdigest()
    return CACHE_DIR / f"hospitals_{key}.json"


def _is_cache_valid(path: Path) -> bool:
    return path.exists() and (time.time() - path.stat().st_mtime) < CACHE_TTL


def _geocode(location: str):
    try:
        resp = requests.get(
            NOMINATIM_URL,
            params={"q": f"{location}, India", "format": "json", "limit": 1},
            headers=HEADERS,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception as e:
        logger.warning("Geocoding failed for %s: %s", location, e)
    return None


def _haversine(lat1, lon1, lat2, lon2) -> float:
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    return round(R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)), 2)


def _build_overpass_query(lat: float, lon: float, radius_m: int) -> str:
    return f"""
    [out:json][timeout:30];
    (
      node["amenity"="hospital"](around:{radius_m},{lat},{lon});
      way["amenity"="hospital"](around:{radius_m},{lat},{lon});
      node["amenity"="clinic"](around:{radius_m},{lat},{lon});
      node["healthcare"="hospital"](around:{radius_m},{lat},{lon});
      way["healthcare"="hospital"](around:{radius_m},{lat},{lon});
    );
    out center tags;
    """


def _parse_elements(elements: list) -> list:
    hospitals = []
    seen = set()
    for el in elements:
        tags = el.get("tags", {})
        name = tags.get("name") or tags.get("name:en")
        if not name or name in seen:
            continue
        seen.add(name)
        elat = el.get("lat") or el.get("center", {}).get("lat")
        elon = el.get("lon") or el.get("center", {}).get("lon")
        if not elat or not elon:
            continue
        hospitals.append({
            "name": name,
            "address": ", ".join(filter(None, [
                tags.get("addr:housenumber"),
                tags.get("addr:street"),
                tags.get("addr:suburb"),
                tags.get("addr:city"),
            ])) or tags.get("addr:full", "Address not available"),
            "latitude": float(elat),
            "longitude": float(elon),
            "phone": tags.get("phone") or tags.get("contact:phone", "N/A"),
            "website": tags.get("website") or tags.get("contact:website", "N/A"),
            "type": tags.get("amenity") or tags.get("healthcare", "hospital"),
            "beds": tags.get("beds", "N/A"),
            "emergency": tags.get("emergency", "N/A"),
            "speciality": tags.get("healthcare:speciality", "General"),
        })
    return hospitals


def _fetch_hospitals_overpass(lat: float, lon: float) -> list:
    for radius in [8000, 15000, 25000]:
        for url in OVERPASS_URLS:
            try:
                logger.info("Querying %s radius=%dm", url, radius)
                resp = requests.post(
                    url,
                    data={"data": _build_overpass_query(lat, lon, radius)},
                    headers=HEADERS,
                    timeout=35,
                )
                resp.raise_for_status()
                hospitals = _parse_elements(resp.json().get("elements", []))
                if hospitals:
                    logger.info("Found %d hospitals via %s radius=%dm", len(hospitals), url, radius)
                    return hospitals
            except requests.exceptions.Timeout:
                logger.warning("Timeout: %s radius=%dm", url, radius)
            except Exception as e:
                logger.warning("Overpass error %s: %s", url, e)
        time.sleep(1)
    return []


def _score_hospital(h: dict, center_lat: float, center_lon: float, specialty: str) -> dict:
    dist = _haversine(center_lat, center_lon, h["latitude"], h["longitude"])
    dist_score = max(0.0, 1.0 - dist / 25.0)
    spec_score = 0.3 if specialty.lower() in h.get("speciality", "").lower() else 0.0
    emg_score = 0.1 if str(h.get("emergency", "")).lower() in ("yes", "24/7") else 0.0
    total = round(dist_score * 0.6 + spec_score + emg_score, 4)
    h["distance_km"] = dist
    h["relevance_score"] = total
    return h


def get_hospitals(location: str, specialty: str, limit: int = 5) -> dict:
    cache_path = _cache_key(location)

    if _is_cache_valid(cache_path):
        logger.info("Cache hit for hospitals in %s", location)
        cached = json.loads(cache_path.read_text())
        hospitals = cached["hospitals"]
        center = cached["center"]
    else:
        coords = _geocode(location)
        if not coords:
            return {
                "hospitals": [],
                "total_found": 0,
                "center": None,
                "source": "error",
                "error": f"Could not geocode location: {location}",
            }
        lat, lon = coords
        center = {"lat": lat, "lon": lon}
        hospitals = _fetch_hospitals_overpass(lat, lon)
        # Only cache non-empty results so we retry on next request if empty
        if hospitals:
            cache_path.write_text(json.dumps({"hospitals": hospitals, "center": center}))
        logger.info("Fetched %d hospitals for %s", len(hospitals), location)

    lat, lon = center["lat"], center["lon"]
    scored = [_score_hospital(h, lat, lon, specialty) for h in hospitals]
    scored.sort(key=lambda x: x["relevance_score"], reverse=True)

    return {
        "hospitals": scored[:limit],
        "total_found": len(scored),
        "center": center,
        "source": "OpenStreetMap (Overpass API)",
    }
