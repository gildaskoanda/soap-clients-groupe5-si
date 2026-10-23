"""Règles de qualité et de transformation. Elles reprennent celles du service SOAP (ClientValidator.php)."""
import re
from datetime import date, datetime

CODE_RE = re.compile(r"^CLI-\d{6}$")
NAME_RE = re.compile(r"^[^\W\d_](?:[^\W\d_]|[ '\-]){1,79}$")
PHONE_RE = re.compile(r"^\+?[0-9][0-9 ]{7,17}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
STATUTS = {"actif", "inactif", "suspendu"}

# Champs métier synchronisés dans les deux sens
BUSINESS_FIELDS = ("nom", "prenom", "email", "telephone", "ville", "pays", "statut", "date_inscription")


def validate(row: dict) -> list:
    """Retourne la liste des motifs de rejet (vide si la ligne est valide)."""
    reasons = []
    code = (row.get("code_client") or "").strip()
    if not CODE_RE.match(code):
        reasons.append("code_client_invalide")
    for f in ("nom", "prenom"):
        v = (row.get(f) or "").strip()
        if not v:
            reasons.append(f"{f}_manquant")
        elif not NAME_RE.match(v):
            reasons.append(f"{f}_invalide")
    email = (row.get("email") or "").strip()
    if not email:
        reasons.append("email_manquant")
    elif len(email) > 190 or not EMAIL_RE.match(email):
        reasons.append("email_invalide")
    phone = (row.get("telephone") or "").strip()
    if phone and not PHONE_RE.match(phone):
        reasons.append("telephone_invalide")
    if (row.get("statut") or "") not in STATUTS:
        reasons.append("statut_invalide")
    return reasons


def _iso(v):
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    return v


def transform(row: dict) -> dict:
    """Normalise une ligne valide en document MongoDB (sans les champs de gestion de version)."""
    return {
        "code_client": row["code_client"].strip(),
        "nom": row["nom"].strip().upper(),
        "prenom": row["prenom"].strip().title(),
        "email": row["email"].strip().lower(),
        "telephone": (row.get("telephone") or "").strip() or None,
        "ville": (row.get("ville") or "").strip() or None,
        "pays": (row.get("pays") or "").strip() or None,
        "statut": row["statut"],
        "date_inscription": _iso(row.get("date_inscription")),
    }
