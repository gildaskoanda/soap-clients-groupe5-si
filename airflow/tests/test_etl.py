"""Tests unitaires de l'ETL et de la réconciliation (MongoDB simulé avec mongomock, MySQL simulé)."""
import os
import sys
from datetime import datetime

import mongomock
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "dags"))
from clients_etl import etl, rules  # noqa: E402
from clients_etl.reconcile import reconcile  # noqa: E402


def row(i, **over):
    r = {"id": i, "code_client": f"CLI-{i:06d}", "nom": "kone", "prenom": "aminata", "email": f"a{i}@example.bf",
         "telephone": "+226 70 11 22 33", "ville": "Bobo-Dioulasso", "pays": "Burkina Faso", "statut": "actif",
         "date_inscription": "2025-01-02", "updated_at": "2026-10-01T08:00:00"}
    r.update(over)
    return r


@pytest.fixture
def db():
    d = mongomock.MongoClient()["clients_db"]
    d.clients.create_index("code_client", unique=True)
    d.clients.create_index("email", unique=True)
    return d


def run(db, rows, run_id="r1"):
    valid, rejected = etl.split_quality(rows)
    return etl.load(db, valid, rejected, run_id, len(rows))


# --- règles ------------------------------------------------------------------------------------
def test_validate_ok():
    assert rules.validate(row(1)) == []


@pytest.mark.parametrize("over,reason", [
    ({"email": "a@@b.bf"}, "email_invalide"), ({"email": "sans-arobase"}, "email_invalide"),
    ({"telephone": "12AB"}, "telephone_invalide"), ({"nom": "K0NE"}, "nom_invalide"),
    ({"nom": ""}, "nom_manquant"), ({"prenom": ""}, "prenom_manquant"),
    ({"code_client": "X1"}, "code_client_invalide"), ({"statut": "banni"}, "statut_invalide"),
])
def test_validate_rejects(over, reason):
    assert reason in rules.validate(row(1, **over))


def test_transform_normalizes():
    d = rules.transform(row(1, email="  A1@Example.BF ", telephone=""))
    assert d["nom"] == "KONE" and d["prenom"] == "Aminata" and d["email"] == "a1@example.bf" and d["telephone"] is None


# --- ETL -----------------------------------------------------------------------------------------
def test_first_load_inserts_and_logs_rejects(db):
    s = run(db, [row(1), row(2), row(3, email="mauvais")])
    assert (s["inserted"], s["rejected"], s["status"]) == (2, 1, "success_with_rejects")
    assert db.clients.count_documents({}) == 2
    assert db.clients_rejected.find_one({"code_client": "CLI-000003"})["reasons"] == ["email_invalide"]
    assert db.etl_runs.count_documents({}) == 1
    doc = db.clients.find_one({"code_client": "CLI-000001"})
    assert doc["version"] == 1 and doc["locally_modified"] is False and doc["sync_status"] == "synced"


def test_idempotent_rerun_changes_nothing(db):
    rows = [row(1), row(2)]
    run(db, rows)
    before = list(db.clients.find({}, {"_id": 0}))
    s = run(db, rows, "r2")
    assert (s["inserted"], s["updated"], s["unchanged"]) == (0, 0, 2)
    assert list(db.clients.find({}, {"_id": 0})) == before   # aucune version incrémentée


def test_source_change_updates_and_bumps_version(db):
    run(db, [row(1)])
    s = run(db, [row(1, ville="Banfora", updated_at="2026-10-02T09:00:00")], "r2")
    d = db.clients.find_one({"code_client": "CLI-000001"})
    assert s["updated"] == 1 and d["ville"] == "Banfora" and d["version"] == 2


def test_mongo_modified_client_is_not_overwritten(db):
    run(db, [row(1)])
    db.clients.update_one({"code_client": "CLI-000001"}, {"$set": {"ville": "Kaya", "locally_modified": True,
                                                                  "sync_status": "pending_mysql"}, "$inc": {"version": 1}})
    s = run(db, [row(1, ville="Dori", updated_at="2026-10-03T09:00:00")], "r2")
    assert s["conflicts_skipped"] == 1 and db.clients.find_one({"code_client": "CLI-000001"})["ville"] == "Kaya"


def test_rejected_row_cleared_once_fixed(db):
    run(db, [row(1, email="mauvais")])
    assert db.clients_rejected.count_documents({}) == 1
    run(db, [row(1)], "r2")
    assert db.clients_rejected.count_documents({}) == 0 and db.clients.count_documents({}) == 1


def test_duplicate_email_in_batch_rejected(db):
    s = run(db, [row(1, email="dup@example.bf"), row(2, email="dup@example.bf")])
    assert s["inserted"] == 1 and db.clients_rejected.find_one({"code_client": "CLI-000002"})["reasons"] == ["email_duplique_dans_lot"]


# --- réconciliation ------------------------------------------------------------------------------
class FakeMySql:
    def __init__(self, rows):
        self.rows, self.clock, self.fail_on = rows, datetime(2026, 10, 10, 12, 0, 0), set()

    def get_row(self, code):
        return dict(self.rows[code]) if code in self.rows else None

    def update(self, code, fields):
        if code in self.fail_on:
            raise RuntimeError("Duplicate entry (1062)")
        self.rows[code].update(fields)
        self.clock = datetime(2026, 10, 10, 12, 0, self.clock.second + 1)
        self.rows[code]["updated_at"] = self.clock
        return self.clock

    def rollback(self):
        pass


def seed_modified(db, i=1, **over):
    run(db, [row(i)])
    db.clients.update_one({"code_client": f"CLI-{i:06d}"},
                          {"$set": {"ville": "Kaya", "locally_modified": True, "sync_status": "pending_mysql", **over}, "$inc": {"version": 1}})


def mysql_for(db, code="CLI-000001"):
    d = db.clients.find_one({"code_client": code})
    return FakeMySql({code: {"id": 1, "nom": "KONE", "prenom": "Aminata", "email": d["email"], "telephone": None, "ville": "Bobo-Dioulasso",
                             "statut": "actif", "updated_at": d["mysql_updated_at"]}})


def test_reconcile_applies_pending_change(db):
    seed_modified(db)
    my = mysql_for(db)
    st = reconcile(db, my, "rec1")
    d = db.clients.find_one({"code_client": "CLI-000001"})
    assert st["applied"] == 1 and my.rows["CLI-000001"]["ville"] == "Kaya"
    assert d["locally_modified"] is False and d["sync_status"] == "synced" and d["mysql_updated_at"] == my.rows["CLI-000001"]["updated_at"]
    assert db.reconciliation_log.find_one({})["action"] == "applied"


def test_reconcile_is_idempotent(db):
    seed_modified(db)
    my = mysql_for(db)
    reconcile(db, my, "rec1")
    st = reconcile(db, my, "rec2")
    assert st["pending"] == 0


def test_conflict_mongo_wins_and_keeps_audit(db):
    seed_modified(db)
    my = mysql_for(db)
    my.rows["CLI-000001"].update(ville="Dori", updated_at=datetime(2026, 10, 9, 9, 0, 0))   # MySQL modifié entre-temps
    st = reconcile(db, my, "rec1")
    assert st["overwritten_conflicts"] == 1 and my.rows["CLI-000001"]["ville"] == "Kaya"
    assert db.reconciliation_log.find_one({})["mysql_overwritten"]["ville"] == "Dori"


def test_row_missing_in_mysql_flags_conflict(db):
    seed_modified(db)
    st = reconcile(db, FakeMySql({}), "rec1")
    assert st["skipped_missing"] == 1 and db.clients.find_one({"code_client": "CLI-000001"})["sync_status"] == "conflict"


def test_failure_on_one_client_does_not_block_others(db):
    run(db, [row(1), row(2)])
    for c in ("CLI-000001", "CLI-000002"):
        db.clients.update_one({"code_client": c}, {"$set": {"ville": "Kaya", "locally_modified": True}, "$inc": {"version": 1}})
    my = FakeMySql({c: {"id": 1, "nom": "KONE", "prenom": "A", "email": "x", "telephone": None, "ville": "B", "statut": "actif",
                        "updated_at": db.clients.find_one({"code_client": c})["mysql_updated_at"]} for c in ("CLI-000001", "CLI-000002")})
    my.fail_on.add("CLI-000001")
    st = reconcile(db, my, "rec1")
    assert st["failed"] == 1 and st["applied"] == 1
    assert db.clients.find_one({"code_client": "CLI-000001"})["locally_modified"] is True
