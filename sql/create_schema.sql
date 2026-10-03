-- =========================================================
-- Projet BI NASA NEO - creation du schema en etoile
-- SQL Server
-- Correspond a la section 4 (Grille de decision et modele en etoile)
-- du plan de projet.
-- Granularite de la table de faits : un survol (close approach)
-- d'un objet donne a une date donnee.
-- =========================================================

CREATE DATABASE NEO_BI;
GO
USE NEO_BI;
GO

-- ---------------------------------------------------------
-- Dimension Objet
-- ---------------------------------------------------------
-- NOTE : le diametre n'existe pas dans CAD (teste et confirme - champs CAD :
-- des, orbit_id, jd, cd, dist, dist_min, dist_max, v_rel, v_inf, t_sigma_f, h).
-- Il vient d'un enrichissement via NeoWs 'browse', joint sur designation = des.
-- Jointure validee par test direct : 433 Eros -> des='433' (CAD) et
-- designation='433' (NeoWs lookup/browse) - meme valeur des deux cotes.
-- NeoWs renvoie un intervalle (min/max), pas une valeur unique : on garde les deux.
CREATE TABLE Dim_Objet (
    id_objet            INT IDENTITY(1,1) PRIMARY KEY,
    designation         NVARCHAR(50) NOT NULL,      -- champ CAD 'des' = champ NeoWs 'designation'
    diametre_min_km     DECIMAL(10,4) NULL,          -- NeoWs browse : estimated_diameter.kilometers.estimated_diameter_min
    diametre_max_km     DECIMAL(10,4) NULL,          -- NeoWs browse : estimated_diameter.kilometers.estimated_diameter_max
    classe_orbitale     NVARCHAR(50) NULL,
    est_connu_diametre  AS (CASE WHEN diametre_min_km IS NULL THEN 0 ELSE 1 END) -- colonne calculee, tracabilite du nettoyage
);
GO

-- ---------------------------------------------------------
-- Dimension Date
-- ---------------------------------------------------------
CREATE TABLE Dim_Date (
    id_date         INT PRIMARY KEY,         -- format YYYYMMDD, pas d'IDENTITY : cle metier
    date_complete   DATE NOT NULL,
    jour            TINYINT NOT NULL,
    mois            TINYINT NOT NULL,
    annee           SMALLINT NOT NULL,
    trimestre       TINYINT NOT NULL,
    jour_semaine    NVARCHAR(10) NOT NULL    -- pour l'analyse de saisonnalite (cas d'usage 1)
);
GO

-- ---------------------------------------------------------
-- Dimension Danger (dimension "fourre-tout" / junk dimension)
-- ---------------------------------------------------------
-- CORRECTION : CAD n'a PAS de champ 'pha' (confirme par test - champs reels :
-- des, orbit_id, jd, cd, dist, dist_min, dist_max, v_rel, v_inf, t_sigma_f, h).
-- est_pha vient de NeoWs ('is_potentially_hazardous_asteroid'), au meme titre
-- que le diametre, joint sur designation = des (meme regle que Dim_Objet).
-- A l'ETL : pour chaque survol, on lit est_pha sur l'OBJET (Dim_Objet /
-- enrichissement NeoWs, un flag par objet, pas par survol) et on le combine
-- avec les tranches calculees a partir de dist/h du survol lui-meme.
CREATE TABLE Dim_Danger (
    id_danger           INT IDENTITY(1,1) PRIMARY KEY,
    est_pha             BIT NOT NULL,                 -- NeoWs 'is_potentially_hazardous_asteroid', via designation = des
    tranche_distance    NVARCHAR(30) NOT NULL,        -- calculee a l'ETL a partir de dist (CAD) - ex: '< 0.01 UA', '0.01-0.05 UA'
    tranche_taille      NVARCHAR(30) NOT NULL         -- calculee a l'ETL a partir du diametre (Dim_Objet) - ex: '< 50m', '50-150m', '> 150m'
);
GO

-- ---------------------------------------------------------
-- Table de faits : un survol
-- ---------------------------------------------------------
CREATE TABLE Fait_Survol (
    id_survol               BIGINT IDENTITY(1,1) PRIMARY KEY,
    id_objet                INT NOT NULL REFERENCES Dim_Objet(id_objet),
    id_date                 INT NOT NULL REFERENCES Dim_Date(id_date),
    id_danger                INT NOT NULL REFERENCES Dim_Danger(id_danger),
    distance_min_ua          DECIMAL(12,8) NOT NULL,   -- champ CAD 'dist'
    distance_min_km          AS (distance_min_ua * 149597870.7) PERSISTED, -- conversion UA -> km (section 6 du plan)
    vitesse_relative_km_s    DECIMAL(10,4) NOT NULL,   -- champ CAD 'v_rel'
    magnitude_absolue        DECIMAL(6,3) NULL,         -- champ CAD 'h'
    -- les deux flux viennent de CAD (NeoWs feed abandonne, structure JSON imbriquee
    -- testee et jugee inutile puisque CAD couvre deja 1900-2100) : seul le type
    -- de chargement differe, pas la source.
    source_chargement        NVARCHAR(20) NOT NULL DEFAULT 'CAD_HISTORIQUE',  -- 'CAD_HISTORIQUE' ou 'CAD_INCREMENTAL'
    date_insertion            DATETIME2 NOT NULL DEFAULT SYSDATETIME()
);
GO

-- Index utiles pour les cas d'usage (filtrage par date et par niveau de danger)
CREATE INDEX IX_Fait_Survol_Date ON Fait_Survol(id_date);
CREATE INDEX IX_Fait_Survol_Danger ON Fait_Survol(id_danger);
GO
