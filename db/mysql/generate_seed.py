#!/usr/bin/env python3
"""Génère db/mysql/02_seed.sql : 200 clients fictifs + 8 lignes volontairement invalides.

Déterministe (graine fixe) : relancer le script produit le même fichier.
Les 8 lignes « sales » servent à démontrer le contrôle qualité d'Airflow (collection clients_rejected).
"""
import random
from datetime import date, timedelta
from pathlib import Path

rnd = random.Random(2026)
NOMS = ["OUEDRAOGO", "KONE", "TRAORE", "SAWADOGO", "COULIBALY", "SANOGO", "DIALLO", "BARRY", "ZONGO", "KABORE",
        "COMPAORE", "SORE", "OUATTARA", "TIENDREBEOGO", "NIKIEMA", "BAMBA", "SANKARA", "DAO", "SOME", "YAMEOGO",
        "HIEN", "KAMBOU", "TAPSOBA", "BELEM", "ILBOUDO"]
PRENOMS = ["Aminata", "Moussa", "Fatoumata", "Ibrahim", "Awa", "Salif", "Mariam", "Issouf", "Rasmata", "Adama",
           "Alimata", "Boureima", "Safiatou", "Seydou", "Nafissatou", "Oumarou", "Kadidia", "Abdoulaye", "Habibou",
           "Zénabou", "Souleymane", "Ramatou", "Lassina", "Hawa", "Yacouba", "Azèta", "Mamadou", "Clarisse", "Désiré", "Estelle"]
VILLES = ["Bobo-Dioulasso", "Ouagadougou", "Koudougou", "Banfora", "Ouahigouya", "Dédougou", "Fada N'Gourma",
          "Kaya", "Tenkodogo", "Dori"]
STATUTS = ["actif"] * 7 + ["inactif"] * 2 + ["suspendu"]


def q(v):
    return "NULL" if v is None else "'" + str(v).replace("\\", "\\\\").replace("'", "''") + "'"


def strip_accents(s):
    return s.lower().translate(str.maketrans("éèêàâîïôùûç' ", "eeeaaiiouuc--"))


rows, used = [], set()
for i in range(1, 201):
    nom, prenom = rnd.choice(NOMS), rnd.choice(PRENOMS)
    email = f"{strip_accents(prenom)}.{strip_accents(nom)}{i}@example.bf"
    phone = f"+226 {rnd.choice(['70', '71', '75', '76', '78', '60', '65', '66'])} {rnd.randint(10, 99)} {rnd.randint(10, 99)} {rnd.randint(10, 99)}"
    d = date(2023, 1, 1) + timedelta(days=rnd.randint(0, 1000))
    rows.append((f"CLI-{i:06d}", nom, prenom, email, phone, rnd.choice(VILLES), "Burkina Faso", rnd.choice(STATUTS), d.isoformat()))

# Lignes volontairement invalides (démonstration du contrôle qualité)
bad = [
    ("CLI-000201", "KONE", "Adama", "adama.kone@@example.bf", "+226 70 11 22 33", "Bobo-Dioulasso", "Burkina Faso", "actif", "2025-03-02"),   # e-mail invalide
    ("CLI-000202", "TRAORE", "Awa", "awa.traore-sans-arobase.bf", "+226 71 11 22 33", "Banfora", "Burkina Faso", "actif", "2025-04-12"),       # e-mail invalide
    ("CLI-000203", "DIALLO", "Salif", "salif.diallo203@example.bf", "12AB", "Ouagadougou", "Burkina Faso", "actif", "2025-05-20"),             # téléphone invalide
    ("CLI-000204", "BARRY", "Mariam", "mariam.barry204@example.bf", "+226", "Kaya", "Burkina Faso", "inactif", "2025-06-01"),                  # téléphone invalide
    ("CLI-000205", "K0NE", "Issouf", "issouf.kone205@example.bf", "+226 75 10 20 30", "Dori", "Burkina Faso", "actif", "2025-06-15"),          # nom invalide (chiffre)
    ("CLI-000206", "", "Rasmata", "rasmata206@example.bf", "+226 76 10 20 30", "Dédougou", "Burkina Faso", "actif", "2025-07-01"),             # nom vide
    ("CLI-000207", "ZONGO", "", "zongo207@example.bf", "+226 78 10 20 30", "Tenkodogo", "Burkina Faso", "suspendu", "2025-07-09"),             # prénom vide
    ("CLI-000208", "SORE", "Boureima", "boureima.sore208@example.bf", "+226 60 10 20 30", "Koudougou", "Burkina Faso", "actif", "2025-08-30"),  # valide (témoin)
]
rows += bad

out = ["-- Généré par generate_seed.py : NE PAS MODIFIER À LA MAIN", "SET NAMES utf8mb4;", "",
       "INSERT INTO clients (code_client, nom, prenom, email, telephone, ville, pays, statut, date_inscription) VALUES"]
out.append(",\n".join("(" + ", ".join(q(v) for v in r) + ")" for r in rows) + ";")
Path(__file__).with_name("02_seed.sql").write_text("\n".join(out) + "\n", encoding="utf-8")
print(f"{len(rows)} lignes écrites dans 02_seed.sql")
