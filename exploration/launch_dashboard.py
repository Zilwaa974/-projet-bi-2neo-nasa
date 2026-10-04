"""
Lance le tableau de bord NEO en local, avec plage de dates modifiable
directement dans la page.

Ce script fait tout :
1. demarre un serveur HTTP local qui sert la page ET relaie les appels
   a l'API CAD (cote serveur, donc pas de blocage CORS) via /api/survols
2. ouvre le navigateur sur le tableau de bord

Chaque changement de plage dans la page declenche un nouvel appel a CAD,
via ce serveur - jamais de donnees perimees, jamais de CORS.

Usage :
    pip install requests
    python launch_dashboard.py
"""
import http.server
import json
import socketserver
import urllib.parse
import webbrowser

import requests

PORT = 8000
CAD_URL = "https://ssd-api.jpl.nasa.gov/cad.api"


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlsplit(self.path)

        if parsed.path == "/api/survols":
            self._proxy_cad(urllib.parse.parse_qs(parsed.query))
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
            print(f"-> {cad_data.get('count')} survol(s) recupere(s).")
            payload = {
                "generated_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
                "params": {"date_min": date_min, "date_max": date_max, "dist_max": dist_max},
                "fields": cad_data.get("fields", []),
                "data": cad_data.get("data", []),
                "count": cad_data.get("count", 0),
            }
            self._send_json(payload)
        except Exception as e:
            print(f"Erreur appel CAD : {e}")
            self._send_json({"error": str(e)}, status=502)

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
