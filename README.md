# Projet BI — NASA NEO

Projet BI 3IA IPSA 2025-2026. Thématique : survols d'objets géocroiseurs (Near Earth Objects), pour appuyer des décisions de surveillance planétaire (voir `Plan de projet BI - NASA NEO.docx`, à la racine du dépôt, pour le détail complet : cas d'usage, matrice du bus décisionnel, schéma en étoile).

## Structure du dépôt

```
sql/          -> script de création du schéma SQL Server (schéma en étoile)
exploration/  -> scripts de test des API et tableau de bord local
.env.example  -> modèle de configuration (à copier en .env)
.gitignore    -> exclut .env et les fichiers temporaires du suivi git
```

## 1. Mettre en place le `.env`

Chaque membre du groupe a besoin de sa propre clé API NeoWs pour certains scripts. Cette clé ne doit **jamais** être commitée sur GitHub.

1. Va sur [api.nasa.gov](https://api.nasa.gov), remplis le formulaire (nom + email) — la clé s'affiche instantanément, gratuite, aucune carte bancaire.
2. À la racine du dépôt, copie `.env.example` en `.env` :
   ```
   cp .env.example .env
   ```
3. Ouvre `.env` et remplace `colle_ta_cle_ici` par ta clé :
   ```
   NEOWS_API_KEY=ta_vraie_cle
   ```
4. `.env` est déjà listé dans `.gitignore` : il reste sur ta machine, jamais sur GitHub. Seul `.env.example` (sans vraie clé) est versionné.

## 2. Installer les dépendances

```
pip install requests python-dotenv
```

## 3. Lancer le tableau de bord en direct

```
cd exploration
python launch_dashboard.py
```

Ce script :
- démarre un petit serveur local sur `http://localhost:8000` ;
- ouvre automatiquement `dashboard_live.html` dans ton navigateur ;
- relaie les appels à l'API JPL SBDB (Close-Approach Data, CAD) côté serveur Python — **pas** côté navigateur, car cette API refuse les appels directs depuis une page web (pas d'en-tête CORS, testé et confirmé).

Laisse la fenêtre du terminal ouverte tant que tu utilises la page. `Ctrl+C` arrête le serveur.

## 4. Comprendre l'interface du tableau de bord

| Élément | Rôle |
| --- | --- |
| **Date min / Date max** | La plage de dates sur laquelle chercher des survols. Par défaut : 30 jours avant/après aujourd'hui. |
| **Distance max (UA)** | Ne garde que les survols plus proches que cette distance, en unités astronomiques (0.05 UA ≈ 7,5 millions de km). Plus la valeur est petite, moins d'objets, mais plus proches. |
| **Charger les données** | Envoie la plage choisie au serveur local, qui interroge l'API et renvoie les résultats à jour — jamais de données en cache. |
| **Cartes de statistiques** | *Survols trouvés* (total sur la plage), *à moins de 0.01 UA* (les plus proches), *vitesse moy.* (km/s), *approche la plus proche* (UA) — une vue rapide avant de regarder le détail. |
| **Tableau** | Une ligne par survol, triée par distance croissante. Colonnes : désignation de l'objet (`des` dans l'API), date et heure du survol, distance minimale, vitesse relative, magnitude absolue (plus la magnitude est basse, plus l'objet est gros/brillant). |
| **Pastille « proche / normal »** | Seuil arbitraire (< 0.01 UA) choisi pour illustrer une alerte, **pas** une classification officielle de danger — l'API CAD ne fournit pas de champ de dangerosité (voir note plus bas). |

## 5. Les autres scripts

**`exploration/test_apis.py`** — script de test/exploration des deux API (CAD et NeoWs), utilisé pour valider le format des données avant de construire l'ETL. Pas nécessaire pour faire tourner le tableau de bord, utile pour comprendre d'où viennent les champs.

**`sql/create_schema.sql`** — crée le schéma en étoile dans SQL Server (`Dim_Objet`, `Dim_Date`, `Dim_Danger`, `Fait_Survol`). Chaque colonne est commentée avec sa source exacte (API + champ).

## 6. Points à connaître avant de construire l'ETL

- **CAD ne fournit pas le diamètre ni la dangerosité (PHA).** Ces deux informations viennent de NeoWs (`browse`), jointes sur `designation = des` — règle validée par un test direct (433 Eros donne `433` des deux côtés).
- **Un seul flux de faits.** CAD couvre 1900 à 2100 dans le même format pour l'historique et l'incrémental (en rejouant l'appel avec un `date-min` glissant) — NeoWs `feed` n'est pas utilisé pour les faits, sa structure JSON imbriquée n'apportait rien.
- **CORS.** Aucune des deux API n'autorise les appels directs depuis un navigateur. Toute page qui a besoin de données fraîches doit passer par un petit serveur (comme `launch_dashboard.py`), jamais par un `fetch()` direct côté client.
