#!/usr/bin/env python3
"""Vérifie la découverte des DAG dans l’image Airflow, sans lancer de tâche."""
from airflow.models import DagBag


bag = DagBag(dag_folder="/opt/airflow/dags", include_examples=False)
assert not bag.import_errors, bag.import_errors
expected = {"clients_mysql_to_mongo": 3, "clients_reconcile_mongo_to_mysql": 1}
actual = {name: len(dag.tasks) for name, dag in bag.dags.items()}
assert actual == expected, actual
for dag in bag.dags.values():
    assert dag.catchup is False
    assert dag.max_active_runs == 1
etl = bag.dags["clients_mysql_to_mongo"]
assert etl.get_task("extract_mysql").downstream_task_ids == {"validate_transform"}
assert etl.get_task("validate_transform").downstream_task_ids == {"load_mongo"}
print("OK : 2 DAG, 4 tâches, dépendances correctes, aucune erreur d’import.")
