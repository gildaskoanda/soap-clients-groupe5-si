"""DAG 2 - Réconciliation MongoDB (référence) -> MySQL des clients modifiés via SOAP."""
import os
from datetime import datetime, timedelta

import pymysql
from airflow.decorators import dag, task
from pymongo import MongoClient

from clients_etl.reconcile import MySqlGateway, reconcile


@dag(
    dag_id="clients_reconcile_mongo_to_mysql",
    description="Renvoie vers MySQL les modifications faites dans MongoDB par le service SOAP",
    schedule="30 * * * *",
    start_date=datetime(2026, 10, 1),
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 1, "retry_delay": timedelta(minutes=2)},
    tags=["clients", "reconciliation", "mongodb"],
)
def clients_reconcile_mongo_to_mysql():
    @task
    def reconcile_task(run_id=None):
        db = MongoClient(os.environ["MONGO_URI"], serverSelectionTimeoutMS=5000)[os.environ["MONGO_DB"]]
        conn = pymysql.connect(host=os.environ["MYSQL_HOST"], port=int(os.environ.get("MYSQL_PORT", 3306)),
                               user=os.environ["MYSQL_USER"], password=os.environ["MYSQL_PASSWORD"],
                               database=os.environ["MYSQL_DATABASE"], charset="utf8mb4", connect_timeout=10)
        try:
            stats = reconcile(db, MySqlGateway(conn), run_id)
        finally:
            conn.close()
        if stats["failed"]:
            raise RuntimeError(f"{stats['failed']} client(s) non réconcilié(s) : voir reconciliation_log ({stats})")
        return stats

    reconcile_task()


clients_reconcile_mongo_to_mysql()
