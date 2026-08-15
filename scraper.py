#!/usr/bin/env python3
"""
scraper.py — Alimente data/jobs.geojson à partir de l'API Adzuna.

Domaines couverts : topographie / géomètre / hydrographie / bathymétrie /
LiDAR / géomatique / photogrammétrie-drone / SIG.
Filtre : ne garde que les offres qui semblent de niveau ingénieur
(Bac+5 / Master / "Ingénieur" / "Engineer" / "MSc" dans le titre ou la
description).

Zones couvertes par Adzuna (pas de couverture Chine — voir README) :
  Europe : FR, GB, DE, NL, IT, PL, AT, CH
  Amérique du Nord : US, CA
  Asie : IN, SG

Variables d'environnement requises :
  ADZUNA_APP_ID
  ADZUNA_APP_KEY
(Compte gratuit sur https://developer.adzuna.com/)
"""

import json
import os
import time
from datetime import datetime, timezone

import requests

ADZUNA_APP_ID = os.environ["ADZUNA_APP_ID"]
ADZUNA_APP_KEY = os.environ["ADZUNA_APP_KEY"]

# Jooble est optionnelle : si la clé n'est pas fournie, cette source est
# simplement ignorée (pas d'erreur).
JOOBLE_API_KEY = os.environ.get("JOOBLE_API_KEY", "").strip()

# Nécessaire pour respecter la politique d'usage de Nominatim/OpenStreetMap
# (un User-Agent identifiable est obligatoire).
GEOCODER_USER_AGENT = "geo-jobs-map/1.0 (contact: replace-with-your-email@example.com)"

# Ordre de priorité demandé : Europe > US > Canada > Asie
COUNTRIES = [
    # Europe
    "fr", "gb", "de", "nl", "it", "pl", "at", "ch",
    # Amérique du Nord
    "us", "ca",
    # Asie (couverture Adzuna limitée)
    "in", "sg",
]

KEYWORDS = [
    # Topographie / géomètre
    "topographe", "geometre topographe", "ingenieur geometre",
    "topographic surveyor", "land surveyor engineer",
    # Hydrographie / bathymétrie
    "hydrographe", "hydrographic surveyor", "bathymetric survey",
    "bathymetry engineer",
    # LiDAR
    "lidar engineer", "lidar surveyor", "airborne lidar",
    # Géomatique / SIG
    "geomaticien", "geomatics engineer", "geospatial engineer",
    "GIS engineer",
    # Photogrammétrie / drone
    "photogrammetrie", "photogrammetry engineer", "drone survey engineer",
    "UAV mapping engineer",
]

# Termes indiquant un poste de niveau ingénieur (Bac+5 / Master)
DEGREE_TERMS = [
    "ingenieur", "ingénieur", "engineer", "engineering degree",
    "master", "msc", "m.sc", "bac+5", "bac + 5", "diplome d'ingenieur",
    "graduate engineer", "degree in geomatics", "degree in surveying",
    "degree in engineering",
]

RESULTS_PER_PAGE = 50
MAX_PAGES = 2  # limite les appels API par mot-clé/pays

# Codes pays Adzuna -> nom complet utilisé comme filtre "location" pour Jooble
COUNTRY_NAMES = {
    "fr": "France", "gb": "United Kingdom", "de": "Germany",
    "nl": "Netherlands", "it": "Italy", "pl": "Poland",
    "at": "Austria", "ch": "Switzerland", "us": "United States",
    "ca": "Canada", "in": "India", "sg": "Singapore",
}


def fetch_jobs(country: str, keyword: str, page: int) -> list:
    url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"
    params = {
        "app_id": ADZUNA_APP_ID,
        "app_key": ADZUNA_APP_KEY,
        "what": keyword,
        "results_per_page": RESULTS_PER_PAGE,
        "content-type": "application/json",
    }
    r = requests.get(url, params=params, timeout=30)
    if r.status_code != 200:
        print(f"  [!] {country}/{keyword} p{page} -> HTTP {r.status_code}")
        return []
    return r.json().get("results", [])


def looks_engineer_level(job: dict) -> bool:
    # Adzuna utilise "description", Jooble utilise "snippet" — on couvre les deux.
    text = f"{job.get('title', '')} {job.get('description', '')} {job.get('snippet', '')}".lower()
    return any(term in text for term in DEGREE_TERMS)


def to_feature(job: dict, country: str, keyword: str) -> dict | None:
    lat = job.get("latitude")
    lon = job.get("longitude")
    if lat is None or lon is None:
        return None
    company = (job.get("company") or {}).get("display_name", "N/A")
    location = (job.get("location") or {}).get("display_name", "N/A")
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": {
            "title": job.get("title", "").strip(),
            "company": company,
            "location": location,
            "country": country.upper(),
            "url": job.get("redirect_url"),
            "created": job.get("created"),
            "salary_min": job.get("salary_min"),
            "salary_max": job.get("salary_max"),
            "matched_keyword": keyword,
            "source": "Adzuna",
        },
    }


# --------------------------------------------------------------------------
# Source 2 : Jooble (optionnelle, activée si JOOBLE_API_KEY est définie)
# --------------------------------------------------------------------------

_geocode_cache: dict[str, tuple[float, float] | None] = {}


def geocode(location: str) -> tuple[float, float] | None:
    """Géocode une adresse texte via Nominatim (OpenStreetMap), avec cache
    pour ne jamais interroger deux fois le même lieu et respecter la
    limite d'1 requête/seconde imposée par leur politique d'usage."""
    if not location:
        return None
    if location in _geocode_cache:
        return _geocode_cache[location]

    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": location, "format": "json", "limit": 1},
            headers={"User-Agent": GEOCODER_USER_AGENT},
            timeout=15,
        )
        r.raise_for_status()
        results = r.json()
        coords = (float(results[0]["lat"]), float(results[0]["lon"])) if results else None
    except (requests.RequestException, ValueError, KeyError, IndexError):
        coords = None

    _geocode_cache[location] = coords
    time.sleep(1.0)  # politesse envers l'API gratuite Nominatim
    return coords


def fetch_jooble_jobs(keyword: str, location: str, page: int = 1) -> list:
    url = f"https://jooble.org/api/{JOOBLE_API_KEY}"
    body = {"keywords": keyword, "location": location, "page": page}
    r = requests.post(url, json=body, timeout=30)
    if r.status_code != 200:
        print(f"  [!] Jooble {location}/{keyword} p{page} -> HTTP {r.status_code}")
        return []
    return r.json().get("jobs", [])


def jooble_to_feature(job: dict, country_code: str, keyword: str) -> dict | None:
    location_text = job.get("location", "")
    coords = geocode(location_text)
    if coords is None:
        return None
    lat, lon = coords
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": {
            "title": (job.get("title") or "").strip(),
            "company": job.get("company", "N/A"),
            "location": location_text,
            "country": country_code.upper(),
            "url": job.get("link"),
            "created": job.get("updated"),
            "salary_min": None,
            "salary_max": None,
            "matched_keyword": keyword,
            "source": "Jooble",
        },
    }


def run_jooble(seen_urls: set, features: list) -> None:
    if not JOOBLE_API_KEY:
        print("ℹ️  JOOBLE_API_KEY absente — source Jooble ignorée.")
        return

    print("\n== Jooble ==")
    for country_code, country_name in COUNTRY_NAMES.items():
        for kw in KEYWORDS:
            try:
                results = fetch_jooble_jobs(kw, country_name)
            except requests.RequestException as e:
                print(f"  [!] {country_name}/{kw}: {e}")
                continue
            for job in results:
                url = job.get("link")
                if not url or url in seen_urls:
                    continue
                if not looks_engineer_level(job):
                    continue
                feat = jooble_to_feature(job, country_code, kw)
                if feat:
                    seen_urls.add(url)
                    features.append(feat)
            time.sleep(0.25)


def main():
    seen_urls = set()
    features = []

    for country in COUNTRIES:
        print(f"== {country.upper()} ==")
        for kw in KEYWORDS:
            for page in range(1, MAX_PAGES + 1):
                try:
                    results = fetch_jobs(country, kw, page)
                except requests.RequestException as e:
                    print(f"  [!] {kw} p{page}: {e}")
                    break
                if not results:
                    break
                for job in results:
                    url = job.get("redirect_url")
                    if not url or url in seen_urls:
                        continue
                    if not looks_engineer_level(job):
                        continue
                    feat = to_feature(job, country, kw)
                    if feat:
                        seen_urls.add(url)
                        features.append(feat)
                time.sleep(0.25)  # courtoisie rate-limit

    run_jooble(seen_urls, features)

    geojson = {
        "type": "FeatureCollection",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(features),
        "features": features,
    }

    os.makedirs("data", exist_ok=True)
    with open("data/jobs.geojson", "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)

    print(f"\n✅ {len(features)} offres écrites dans data/jobs.geojson")


if __name__ == "__main__":
    main()
