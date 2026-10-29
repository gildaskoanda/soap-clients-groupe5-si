"""Extraction MySQL, contrôle qualité et chargement idempotent dans MongoDB."""
from datetime import datetime, timezone

from pymongo.errors import DuplicateKeyError, WriteError

from .rules import BUSINESS_FIELDS, transform, validate

EXTRACT_SQL = (
    "SELECT id, code_client, nom, prenom, email, telephone, ville, pays, statut, "
    "date_inscription, updated_at FROM clients ORDER BY id"
)


def extract(mysql_conn) -> list:
    """Lit toute la table source. Les dates sont converties en chaînes ISO (sérialisable en XCom)."""
    with mysql_conn.cursor() as cur:
        cur.execute(EXTRACT_SQL)
        cols = [c[0] for c in cur.description]
        rows = []
        for r in cur.fetchall():
            d = dict(zip(cols, r))
            d["date_inscription"] = d["date_inscription"].isoformat() if d["date_inscription"] else None
            d["updated_at"] = d["updated_at"].isoformat() if d["updated_at"] else None
            rows.append(d)
    return rows


def split_quality(rows: list):
    """Sépare lignes valides (documents prêts à charger) et rejetées (avec motifs). Détecte les e-mails en double dans le lot."""
    valid, rejected, seen_emails = [], [], {}
    for row in rows:
        reasons = validate(row)
        if reasons:
            rejected.append({"code_client": row.get("code_client"), "reasons": reasons, "raw": row})
            continue
        doc = transform(row)
        doc["mysql_id"] = row["id"]
        doc["mysql_updated_at"] = datetime.fromisoformat(row["updated_at"]) if row.get("updated_at") else None
        if doc["email"] in seen_emails:
            rejected.append({"code_client": doc["code_client"], "reasons": ["email_duplique_dans_lot"], "raw": row})
            continue
        seen_emails[doc["email"]] = doc["code_client"]
        valid.append(doc)
    return valid, rejected


def load(db, valid: list, rejected: list, run_id: str, extracted: int, started_at=None, dag_id="clients_mysql_to_mongo") -> dict:
    """Charge dans MongoDB de façon idempotente et journalise l'exécution.

    - nouveau code_client            -> insertion (version 1, sync_status=synced)
    - existant, géré par SOAP        -> NON écrasé, même après réconciliation
    - existant, données différentes  -> mise à jour + version+1
    - existant, identique            -> aucune écriture métier
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    started_at = started_at or now
    clients, rej = db["clients"], db["clients_rejected"]

    codes = [d["code_client"] for d in valid]
    existing = {d["code_client"]: d for d in clients.find({"code_client": {"$in": codes}})} if codes else {}

    rejected = list(rejected)
    stats = {"inserted": 0, "updated": 0, "unchanged": 0, "conflicts_skipped": 0}
    for doc in valid:
        cur = existing.get(doc["code_client"])
        try:
            if cur is None:
                clients.insert_one({**doc, "version": 1, "locally_modified": False,
                                    "sync_status": "synced", "source": "mysql",
                                    "loaded_at": now, "updated_at": now})
                stats["inserted"] += 1
                continue

            previous_ts, incoming_ts = cur.get("mysql_updated_at"), doc.get("mysql_updated_at")
            stale = previous_ts is not None and (incoming_ts is None or incoming_ts < previous_ts)
            if cur.get("locally_modified") or cur.get("source") == "soap" or stale:
                stats["conflicts_skipped"] += 1
                continue

            # Compare-and-set : la fiche doit encore correspondre à notre lecture.
            # La propriété SOAP persiste après réconciliation, même si les dates
            # MySQL sont identiques à la seconde près.
            condition = {"_id": cur["_id"], "version": cur["version"],
                         "locally_modified": {"$ne": True}, "source": {"$ne": "soap"},
                         "mysql_updated_at": previous_ts}
            changed = any(cur.get(f) != doc.get(f) for f in BUSINESS_FIELDS)
            if changed:
                result = clients.update_one(condition, {
                    "$set": {**doc, "updated_at": now, "source": "mysql"}, "$inc": {"version": 1},
                })
                stats["updated" if result.matched_count else "conflicts_skipped"] += 1
            elif previous_ts != incoming_ts:
                result = clients.update_one(condition, {"$set": {"mysql_updated_at": incoming_ts}})
                stats["unchanged" if result.matched_count else "conflicts_skipped"] += 1
            else:
                stats["unchanged"] += 1
        except (DuplicateKeyError, WriteError) as exc:
            # Seules les erreurs de données sont rejetées. Une erreur technique
            # doit faire échouer la tâche pour déclencher la reprise Airflow.
            if exc.code not in (11000, 121):
                raise
            rejected.append({"code_client": doc["code_client"],
                             "reasons": [f"ecriture_refusee:{exc.code}"],
                             "raw": {"message": "Contrainte d’unicité ou de structure non respectée."}})

    # Journal des rejets (idempotent : un document par code_client, nettoyé quand la ligne devient valide)
    if codes:
        rej.delete_many({"code_client": {"$in": codes}})
    for r in rejected:
        rej.replace_one({"code_client": r["code_client"]},
                        {"code_client": r["code_client"], "reasons": r["reasons"], "raw": _stringify(r["raw"]),
                         "run_id": run_id, "rejected_at": now}, upsert=True)

    finished = datetime.now(timezone.utc).replace(tzinfo=None)
    summary = {
        "dag_id": dag_id, "run_id": run_id, "started_at": started_at, "finished_at": finished,
        "extracted": extracted, "valid": len(valid), "rejected": len(rejected), **stats,
        "status": "success" if not rejected else "success_with_rejects",
    }
    db["etl_runs"].insert_one(dict(summary))
    return summary


def _stringify(raw):
    return {k: (v if isinstance(v, (str, int, float, bool, type(None))) else str(v)) for k, v in raw.items()}
