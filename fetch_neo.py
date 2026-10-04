import requests
import pandas as pd


def fetch_neo_data(date_min="1990-01-01", date_max="2026-12-31", dist_max="0.2"):
    url = "https://ssd-api.jpl.nasa.gov/cad.api"
    params = {
        "date-min": date_min,
        "date-max": date_max,
        "dist-max": dist_max,
        "fullname": "true",
    }

    print("Appel API en cours...")
    response = requests.get(url, params=params)
    response.raise_for_status()
    raw = response.json()
    print(f"{raw['count']} survols recuperes depuis l'API")

    # L'API renvoie deux listes separees : fields (noms) et data (valeurs)
    # pd.DataFrame les assemble en table directement
    df = pd.DataFrame(raw["data"], columns=raw["fields"])

    # --- Typage ---
    # Tout arrive en string depuis l'API, on convertit les colonnes numeriques
    # errors="coerce" : valeurs non convertibles -> NaN plutot qu'une exception
    colonnes_numeriques = ["dist", "dist_min", "dist_max", "v_rel", "v_inf", "h"]
    for col in colonnes_numeriques:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Format de date retourne par l'API : "1990-Jan-01 01:05"
    df["cd"] = pd.to_datetime(df["cd"], format="%Y-%b-%d %H:%M")

    # --- Enrichissement ---
    # Conversion UA -> km pour la lisibilite dans Power BI
    df["dist_min_km"] = df["dist_min"] * 149_597_870

    # Dimensions temporelles pour Dim_Date
    df["annee"]     = df["cd"].dt.year
    df["mois"]      = df["cd"].dt.month
    df["trimestre"] = df["cd"].dt.quarter

    # Tranches de distance pour Dim_Danger
    # pd.cut transforme une valeur continue en categorie selon des seuils fixes
    df["tranche_distance"] = pd.cut(
        df["dist_min"],
        bins=[0, 0.05, 0.1, 0.2, float("inf")],
        labels=["tres proche", "proche", "modere", "lointain"],
    )

    return df


if __name__ == "__main__":
    df = fetch_neo_data()

    print(f"\nApercu des donnees ({df.shape[0]} lignes, {df.shape[1]} colonnes) :")
    print(df[["fullname", "cd", "dist_min", "dist_min_km", "v_rel", "h", "tranche_distance"]].head(10).to_string())

    print(f"\nValeurs manquantes par colonne :")
    print(df.isnull().sum()[df.isnull().sum() > 0])

    output_path = "neo_close_approaches.csv"
    # utf-8-sig : ajoute un BOM pour que Excel et SSIS ouvrent le fichier sans probleme d'encodage
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"\nExport termine : {output_path}")
