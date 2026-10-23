# Plan de tests et résultats attendus

## 1. Vue d'ensemble

| # | Niveau | Outil | Fichier | Nombre |
|---|---|---|---|---|
| A | Fonctionnel SOAP (WSDL, opérations, Faults, panne) | Python (stdlib) | `tests/e2e/run_soap_tests.py` | 20 cas |
| B | ETL + réconciliation (logique) | pytest + mongomock | `airflow/tests/test_etl.py` | 21 tests |
| C | Manuel SOAP | SoapUI | `tests/soapui/requests/*.xml` | 11 requêtes |
| D | **Bout en bout de la chaîne principale** | shell + SoapUI | §3 ci-dessous | 1 scénario |

Résultats déjà obtenus (sans Docker) : `RESULTATS_TESTS_HARNESS.md` (A, 20/20) et `RESULTATS_PYTEST.txt` (B, 21/21).

## 2. Cas du test A (extraits — liste complète dans `RESULTATS_TESTS_HARNESS.md`)

| Cas | Entrée | Résultat attendu |
|---|---|---|
| T01 | `GET /soap/clients?wsdl` | HTTP 200, 3 opérations, pas de marqueur `__ENDPOINT__` |
| T02 | `getClientDetails CLI-000010` | HTTP 200, client avec `version` |
| T03 | `getClientDetails CLI-999999` | HTTP 500, Fault `Client` / `CLIENT_NOT_FOUND` |
| T04 | `getClientDetails ABC` | Fault `VALIDATION_ERROR`, champ `codeClient` |
| T06 | `searchClients statut=actif page=2 taillePage=3` | 3 clients, `total > 3` |
| T07 | `searchClients taillePage=1000` | Fault `VALIDATION_ERROR`, champ `taillePage` |
| T10 | `updateClient ville + statut` | HTTP 200, `version+1`, `synchronisation=pending_mysql` |
| T12 | `updateClient` avec ancienne `versionAttendue` | Fault `VERSION_CONFLICT` |
| T14 | `updateClient` e-mail d'un autre client | Fault `EMAIL_ALREADY_USED` |
| T19 | `docker compose stop mongo` puis `getClientDetails` | Fault `Server` / `SERVICE_UNAVAILABLE` |
| T20 | `docker compose start mongo` puis `getClientDetails` | HTTP 200 (reprise automatique) |

Exécution : `python3 tests/e2e/run_soap_tests.py --db-down docker --report docs/RESULTATS_TESTS_DOCKER.md`

## 3. Scénario de bout en bout (obligatoire) : MySQL → Airflow → MongoDB → SOAP → MongoDB → Airflow → MySQL

| Étape | Action | Résultat attendu |
|---|---|---|
| 1 | `docker compose up -d --build` puis `docker compose ps` | mysql, mongo, laravel : `healthy` |
| 2 | `docker compose exec mysql mysql -uapp -papp_password clients_src -e "SELECT COUNT(*) FROM clients"` | **208** |
| 3 | `docker compose exec airflow-scheduler airflow dags trigger clients_mysql_to_mongo` puis attendre ~30 s | DAG en `success` (UI : <http://localhost:8081>) |
| 4 | `mongosh` : `db.clients.countDocuments()` et `db.clients_rejected.countDocuments()` | **201** et **7** ; `db.etl_runs.find().sort({finished_at:-1}).limit(1)` → `inserted: 201, rejected: 7` |
| 5 | Relancer le DAG 1 (idempotence) | `etl_runs` : `inserted: 0, updated: 0, unchanged: 201` |
| 6 | SoapUI : `getClientDetails CLI-000010` | client, `version 1`, `synchronisation synced` |
| 7 | SoapUI : `updateClient CLI-000010 ville=Ouagadougou` | `version 2`, `synchronisation pending_mysql` |
| 8 | MySQL : `SELECT ville FROM clients WHERE code_client='CLI-000010'` | **ancienne ville** (MySQL pas encore à jour : écriture uniquement dans la référence) |
| 9 | Zabbix (ou `curl localhost:8080/monitoring/stats`) | `pending_reconciliation: 1` |
| 10 | `docker compose exec airflow-scheduler airflow dags trigger clients_reconcile_mongo_to_mysql` puis attendre ~20 s | DAG `success` |
| 11 | MySQL : même `SELECT` qu'à l'étape 8 | **Ouagadougou** |
| 12 | `getClientDetails CLI-000010` | `synchronisation synced`, `version 2` |
| 13 | `db.reconciliation_log.find({code_client:'CLI-000010'})` | une entrée `action: "applied"` |
| 14 | Conflit : modifier la ville dans MySQL **et** via SOAP, relancer le DAG 2 | `applied_conflict_mongo_wins`, la ville SOAP l'emporte, ancienne ligne MySQL dans `mysql_overwritten` |

## 4. Tests SoapUI (manuels)
1. *File → New SOAP Project* ; *Initial WSDL* : `http://localhost:8080/soap/clients?wsdl` ; cocher *Create sample requests*.
2. Pour chaque fichier de `tests/soapui/requests/`, copier le corps dans une requête de l'opération correspondante (le commentaire en tête de fichier donne le résultat attendu).
3. Ajouter des assertions : *SOAP Response*, *Not SOAP Fault* (cas passants), *SOAP Fault* (cas d'erreur), *XPath Match* sur `//*:code` pour vérifier le code de Fault.
4. *Indisponibilité base* : `docker compose stop mongo`, rejouer `01_getClientDetails_ok` → Fault `SERVICE_UNAVAILABLE` ; `docker compose start mongo`.

## 5. Tests unitaires ETL
`pip install -r airflow/requirements-dev.txt && pytest airflow/tests -v` — couvre règles de qualité (8 motifs de rejet), première charge, **idempotence** (aucune version incrémentée au 2ᵉ passage), mise à jour depuis la source, **non-écrasement** d'un client modifié dans Mongo, nettoyage des rejets corrigés, doublons d'e-mail dans le lot, réconciliation (appliquée, idempotente, conflit « Mongo gagne », ligne absente, échec isolé).
