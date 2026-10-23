"""DAG 1 - Chargement des clients MySQL -> MongoDB (extraction, contrôle qualité, chargement idempotent)."""
import os
from datetime import datetime, timedelta

import pymysql
from airflow.decorators import dag, task
from pymongo import MongoClient

from clients_etl import etl


def mysql_conn():
    return pymysql.connect(host=os.environ["MYSQL_HOST"], port=int(os.environ.get("MYSQL_PORT", 3306)),
                           user=os.environ["MYSQL_USER"], password=os.environ["MYSQL_PASSWORD"],
                           database=os.environ["MYSQL_DATABASE"], charset="utf8mb4", connect_timeout=10)


def mongo_db():
    return MongoClient(os.environ["MONGO_URI"], serverSelectionTimeoutMS=5000)[os.environ["MONGO_DB"]]


@dag(
    dag_id="clients_mysql_to_mongo",
    description="MySQL -> contrôle qualité -> MongoDB (base de référence), idempotent",
    schedule="@hourly",
    start_date=datetime(2026, 10, 1),
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=1)},
    tags=["clients", "etl", "mongodb"],
)
def clients_mysql_to_mongo():
    @task
    def extract_mysql():
        conn = mysql_conn()
        try:
            return etl.extract(conn)
        finally:
            conn.close()

    @task
    def validate_transform(rows: list):
        valid, rejected = etl.split_quality(rows)
        # datetime -> ISO pour la sérialisation XCom ; reconvertis au chargement
        for d in valid:
            d["mysql_updated_at"] = d["mysql_updated_at"].isoformat() if d["mysql_updated_at"] else None
        return {"valid": valid, "rejected": rejected, "extracted": len(rows)}

    @task
    def load_mongo(payload: dict, run_id=None):
        for d in payload["valid"]:
            d["mysql_updated_at"] = datetime.fromisoformat(d["mysql_updated_at"]) if d["mysql_updated_at"] else None
        summary = etl.load(mongo_db(), payload["valid"], payload["rejected"], run_id, payload["extracted"])
        return {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in summary.items()}

    load_mongo(validate_transform(extract_mysql()))


clients_mysql_to_mongo()
