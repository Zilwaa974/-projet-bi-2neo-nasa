"""
Script de test des deux API NASA/JPL pour le projet BI NEO.
A lancer en LOCAL, sur une machine qui a un acces internet normal
(pas dans cet environnement Claude, dont le reseau est restreint).

Usage :
    pip install requests python-dotenv
    cp .env.example .env     (une seule fois, puis mets TA cle dans .env)
    python test_apis.py
"""
import json
import os
import sys

import requests
from dotenv import load_dotenv

# Charge les variables du fichier .env (jamais commite, voir .gitignore)
# dans l'environnement du process. Chaque membre du groupe a son propre
# .env en local avec sa propre cle.
load_dotenv()

NEOWS_API_KEY = os.environ.get("NEOWS_API_KEY")


def test_cad(date_min="2024-01-01", date_max="2024-01-31", dist_max="0.05"):
    """JPL SBDB Close-Approach Data API - pas de cle requise."""
    url = "https://ssd-api.jpl.nasa.gov/cad.api"
    params = {"date-min": date_min, "date-max": date_max, "dist-max": dist_max}
    print(f"--- CAD API : {date_min} -> {date_max}, dist-max={dist_max} AU ---")
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    print("count:", data.get("count"))
    print("fields:", data.get("fields"))
    print("exemple de ligne:", data.get("data", [None])[0])
    return data


def test_neows_feed(api_key="DEMO_KEY", start_date="2024-01-01", end_date="2024-01-02"):
    """NeoWs feed - fenetre max 7 jours, necessite une cle API.
    N'est plus utilise pour les faits (CAD couvre deja l'incremental) ;
    sert ici a verifier si le champ 'designation' correspond au 'des' de CAD
    (ex. '2024 AV2' trouve par CAD le 2024-01-01)."""
    url = "https://api.nasa.gov/neo/rest/v1/feed"
    params = {"start_date": start_date, "end_date": end_date, "api_key": api_key}
    print(f"\n--- NeoWs feed : {start_date} -> {end_date} ---")
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    print("element_count:", data.get("element_count"))
    for day, objs in data.get("near_earth_objects", {}).items():
        for obj in objs:
            print(f"  {day} | id: {obj.get('id')} | name: {obj.get('name')} | "
                  f"designation: {obj.get('designation')}")
    # Limites restantes visibles dans les headers de reponse
    print("Rate limit restante:", r.headers.get("X-RateLimit-Remaining"))
    return data


def test_neows_browse(api_key="DEMO_KEY", page=0):
    """NeoWs browse - catalogue complet des NEO, avec diametre estime deja calcule.
    Role : enrichir Dim_Objet en diametre (CAD ne fournit pas ce champ).
    Point a verifier : la cle de jointure avec le 'des' de CAD."""
    url = "https://api.nasa.gov/neo/rest/v1/neo/browse"
    params = {"page": page, "size": 5, "api_key": api_key}
    print(f"\n--- NeoWs browse : page {page} ---")
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    print("page info:", data.get("page"))
    # affiche tous les objets de la page (pas juste le premier) : "433 Eros" est nomme,
    # donc pas representatif - on veut voir un objet avec une designation provisoire
    # du type "2024 AV2" comme dans l'exemple CAD, pour comparer directement.
    for obj in data.get("near_earth_objects", []):
        print("id:", obj.get("id"), "| name:", obj.get("name"),
              "| name_limited:", obj.get("name_limited"),
              "| designation:", obj.get("designation"))  # candidat le plus probable pour joindre avec 'des' de CAD
    print("Rate limit restante:", r.headers.get("X-RateLimit-Remaining"))
    return data


def test_cad_large_range():
    """Verifie le volume reel sur une plage longue - point a confirmer avant de s'engager."""
    print("\n--- CAD API : volume sur 10 ans (2015-2025), dist-max=0.05 AU ---")
    data = test_cad(date_min="2015-01-01", date_max="2025-01-01", dist_max="0.05")
    print(f"=> {data.get('count')} survols sur 10 ans. Extrapole sur 1990-2026 (~36 ans) : "
          f"~{int(data.get('count', 0)) * 36 // 10} lignes environ (ordre de grandeur, pas une projection exacte).")


def test_match_single_object(api_key, neo_id="2000433"):
    """Test definitif sur UN SEUL objet (433 Eros) : quel 'des' utilise CAD,
    et quel champ NeoWs (lookup complet, pas feed/browse) y correspond ?"""
    print(f"\n--- Comparaison directe sur un seul objet (NeoWs id {neo_id} = 433 Eros) ---")

    # Cote NeoWs : lookup complet (contrairement a feed/browse, lookup renvoie
    # systematiquement 'designation' rempli, car c'est l'enregistrement complet).
    r1 = requests.get(f"https://api.nasa.gov/neo/rest/v1/neo/{neo_id}",
                       params={"api_key": api_key}, timeout=30)
    r1.raise_for_status()
    neo = r1.json()
    print("NeoWs lookup -> name:", neo.get("name"),
          "| designation:", neo.get("designation"))

    # Cote CAD : on cherche cet objet par son numero officiel (sans filtre de distance,
    # sinon il risque de n'avoir aucun survol recent dans la fenetre par defaut).
    r2 = requests.get("https://ssd-api.jpl.nasa.gov/cad.api",
                       params={"des": "433", "date-min": "1900-01-01", "date-max": "2100-01-01",
                               "dist-max": "1"}, timeout=30)
    r2.raise_for_status()
    cad = r2.json()
    print("CAD -> count:", cad.get("count"))
    if cad.get("data"):
        print("CAD -> des (1ere ligne):", cad["data"][0][0])


if __name__ == "__main__":
    if not NEOWS_API_KEY:
        print("!! NEOWS_API_KEY absente. Copie .env.example en .env et mets ta cle dedans "
              "(obtenue sur https://api.nasa.gov).", file=sys.stderr)
        sys.exit(1)

    try:
        test_cad()
    except Exception as e:
        print("Erreur CAD API:", e, file=sys.stderr)

    try:
        test_cad_large_range()
    except Exception as e:
        print("Erreur CAD API (volume):", e, file=sys.stderr)

    try:
        test_neows_browse(api_key=NEOWS_API_KEY)
    except Exception as e:
        print("Erreur NeoWs browse:", e, file=sys.stderr)

    try:
        test_match_single_object(api_key=NEOWS_API_KEY)
    except Exception as e:
        print("Erreur comparaison single object:", e, file=sys.stderr)

    # reactive temporairement pour verifier la correspondance designation <-> des de CAD
    try:
        test_neows_feed(api_key=NEOWS_API_KEY)
    except Exception as e:
        print("Erreur NeoWs feed:", e, file=sys.stderr)
