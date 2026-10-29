"""Réconciliation MongoDB (référence) -> MySQL des clients modifiés via le service SOAP.

Politique : MongoDB est la source de vérité. Si la ligne MySQL a changé depuis la dernière synchronisation
(conflit), la valeur MongoDB l'emporte, l'état MySQL écrasé est conservé dans reconciliation_log.
"""
from datetime import datetime, timezone

SYNC_FIELDS = ("nom", "prenom", "email", "telephone", "ville", "statut")


class MySqlGateway:
    """Accès MySQL minimal (injectable pour les tests)."""

    def __init__(self, conn):
        self.conn = conn

    def get_row(self, code_client):
        with self.conn.cursor() as cur:
            cur.execute("SELECT id, nom, prenom, email, telephone, ville, statut, updated_at FROM clients WHERE code_client=%s FOR UPDATE", (code_client,))
            r = cur.fetchone()
            if r is None:
                return None
            return dict(zip([c[0] for c in cur.description], r))

    def update(self, code_client, fields: dict):
        """Applique les champs et retourne le nouvel updated_at MySQL."""
        assignments = ", ".join(f"{k}=%s" for k in fields)
        with self.conn.cursor() as cur:
            cur.execute(f"UPDATE clients SET {assignments} WHERE code_client=%s", (*fields.values(), code_client))
            cur.execute("SELECT updated_at FROM clients WHERE code_client=%s", (code_client,))
            new_ts = cur.fetchone()[0]
        self.conn.commit()
        return new_ts

    def rollback(self):
        self.conn.rollback()


def reconcile(db, mysql: MySqlGateway, run_id: str) -> dict:
    clients, log = db["clients"], db["reconciliation_log"]
    stats = {"pending": 0, "applied": 0, "overwritten_conflicts": 0, "skipped_missing": 0, "failed": 0, "raced": 0}

    for doc in list(clients.find({"locally_modified": True})):
        stats["pending"] += 1
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        entry = {"run_id": run_id, "code_client": doc["code_client"], "version": doc["version"], "ts": now}
        condition = {"_id": doc["_id"], "version": doc["version"]}
        try:
            row = mysql.get_row(doc["code_client"])
            if row is None:
                mysql.rollback()
                clients.update_one(condition, {"$set": {"sync_status": "conflict"}})
                log.insert_one({**entry, "action": "skipped_missing_in_mysql"})
                stats["skipped_missing"] += 1
                continue

            conflict = row["updated_at"] != doc.get("mysql_updated_at")
            fields = {f: doc.get(f) for f in SYNC_FIELDS}
            new_ts = mysql.update(doc["code_client"], fields)

            # Journaliser avant l'acquittement : si le journal échoue, la fiche
            # demeure en attente et le retour MySQL peut être rejoué.
            action = "applied_conflict_mongo_wins" if conflict else "applied"
            audit = {**entry, "action": action}
            if conflict:
                audit["mysql_overwritten"] = {
                    k: (str(v) if k == "updated_at" else v) for k, v in row.items()
                }
            log.insert_one(audit)

            # N'efface le drapeau que si aucune nouvelle écriture SOAP n'a eu lieu entre-temps.
            res = clients.update_one(condition,
                                     {"$set": {"locally_modified": False, "sync_status": "synced", "mysql_updated_at": new_ts}})
            if res.modified_count == 0:
                stats["raced"] += 1
                log.insert_one({**entry, "action": "applied_but_new_change_pending"})
                continue

            if conflict:
                stats["overwritten_conflicts"] += 1
            else:
                stats["applied"] += 1
        except Exception as e:  # noqa: BLE001 - une ligne en échec ne bloque pas les suivantes
            try:
                mysql.rollback()
            except Exception:  # noqa: BLE001
                pass
            clients.update_one(condition, {"$set": {"sync_status": "conflict"}})
            log.insert_one({**entry, "action": "failed", "error": f"{type(e).__name__}: {e}"})
            stats["failed"] += 1
    return stats
