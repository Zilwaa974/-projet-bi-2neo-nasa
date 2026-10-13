"""
Lance le tableau de bord NEO en local, avec plage de dates modifiable
directement dans la page.

Ce script fait tout :
1. demarre un serveur HTTP local qui sert la page ET relaie les appels
   a l'API CAD (cote serveur, donc pas de blocage CORS) via /api/survols
2. ouvre le navigateur sur le tableau de bord

Deux sources possibles pour /api/survols, choisies par la page via
le parametre ?source= :
- source=api (defaut) : appel en direct a l'API CAD (donnees a jour,
  mais a besoin d'internet et peut etre un peu lente sur de grandes plages)
- source=csv : lit neo_close_approaches.csv (a la racine du projet),
  genere par fetch_neo.py - memes champs que l'API (des, cd, dist, v_rel, h),
  couvre 1990-2026, instantane, fonctionne sans internet.

Usage :
    pip install requests
    python launch_dashboard.py
"""
import csv
import http.server
import json
import socketserver
import urllib.parse
import webbrowser
from pathlib import Path

import requests

PORT = 8000
CAD_URL = "https://ssd-api.jpl.nasa.gov/cad.api"

# neo_close_approaches.csv est a la racine du projet, ce script est dans exploration/
CSV_PATH = Path(__file__).resolve().parent.parent / "neo_close_approaches.csv"

# champs qu'on renvoie depuis le CSV, dans le meme ordre/sens que l'API CAD
# pour que le front-end (dashboard_live.html) n'ait pas a distinguer les sources
CSV_FIELDS = ["des", "cd", "dist", "v_rel", "h"]

_csv_cache = None  # charge une seule fois, puis garde en memoire (72k+ lignes)


def load_csv():
    global _csv_cache
    if _csv_cache is None:
        if not CSV_PATH.exists():
            raise FileNotFoundError(f"Fichier introuvable : {CSV_PATH}")
        rows = []
        with open(CSV_PATH, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
        _csv_cache = rows
        print(f"CSV charge en memoire : {len(rows)} lignes depuis {CSV_PATH.name}")
    return _csv_cache


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlsplit(self.path)

        if parsed.path == "/api/survols":
            qs = urllib.parse.parse_qs(parsed.query)
            source = qs.get("source", ["api"])[0]
            if source == "csv":
                self._serve_csv(qs)
            else:
                self._proxy_cad(qs)
            return

        # sinon, comportement normal : sert les fichiers statiques (le .html)
        super().do_GET()

    def _proxy_cad(self, qs):
        date_min = qs.get("date_min", [""])[0]
        date_max = qs.get("date_max", [""])[0]
        dist_max = qs.get("dist_max", ["0.05"])[0]

        if not date_min or not date_max:
            self._send_json({"error": "date_min et date_max requis"}, status=400)
            return

        print(f"Relais vers CAD : {date_min} -> {date_max}, dist-max={dist_max} AU ...")
        try:
            r = requests.get(
                CAD_URL,
                params={"date-min": date_min, "date-max": date_max, "dist-max": dist_max},
                timeout=30,
            )
            r.raise_for_status()
            cad_data = r.json()
            print(f"-> {cad_data.get('count')} survol(s) recupere(s) via l'API.")
            payload = {
                "generated_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
                "params": {"date_min": date_min, "date_max": date_max, "dist_max": dist_max},
                "source": "api",
                "fields": cad_data.get("fields", []),
                "data": cad_data.get("data", []),
                "count": cad_data.get("count", 0),
            }
            self._send_json(payload)
        except Exception as e:
            print(f"Erreur appel CAD : {e}")
            self._send_json({"error": str(e)}, status=502)

    def _serve_csv(self, qs):
        date_min = qs.get("date_min", [""])[0]
        date_max = qs.get("date_max", [""])[0]
        dist_max = qs.get("dist_max", ["0.05"])[0]

        if not date_min or not date_max:
            self._send_json({"error": "date_min et date_max requis"}, status=400)
            return
        try:
            dist_max_f = float(dist_max)
        except ValueError:
            self._send_json({"error": "dist_max invalide"}, status=400)
            return

        print(f"Lecture CSV : {date_min} -> {date_max}, dist-max={dist_max} AU ...")
        try:
            rows = load_csv()
        except FileNotFoundError as e:
            self._send_json({"error": str(e)}, status=404)
            return

        matched = []
        for row in rows:
            cd = row.get("cd", "")
            cd_date = cd[:10]  # "YYYY-MM-DD HH:MM:SS" -> "YYYY-MM-DD"
            if not (date_min <= cd_date <= date_max):
                continue
            try:
                dist_val = float(row.get("dist", ""))
            except ValueError:
                continue
            if dist_val > dist_max_f:
                continue
            matched.append([row.get(f, "") for f in CSV_FIELDS])

        print(f"-> {len(matched)} survol(s) trouve(s) dans le CSV.")
        payload = {
            "generated_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
            "params": {"date_min": date_min, "date_max": date_max, "dist_max": dist_max},
            "source": "csv",
            "fields": CSV_FIELDS,
            "data": matched,
            "count": len(matched),
        }
        self._send_json(payload)

    def _send_json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass  # on garde juste nos propres prints, moins de bruit dans le terminal


def start_server_and_open():
    httpd = socketserver.ThreadingTCPServer(("", PORT), Handler)
    url = f"http://localhost:{PORT}/dashboard_live.html"
    print(f"Serveur demarre : {url}")
    webbrowser.open(url)
    print("Laisse cette fenetre ouverte tant que tu utilises le tableau de bord.")
    print("Ctrl+C pour arreter le serveur.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nArret du serveur.")
        httpd.shutdown()


if __name__ == "__main__":
    start_server_and_open()
