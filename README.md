# Service SOAP de clients — Laravel · Airflow · MongoDB · Zabbix

Projet *Développement à base de composants et services web* — IBAM, 2026 — **Groupe 5 SI, thème n° 7**.

> **Membres du groupe (Sécurité informatique — SI)**
>
> | Nom | Prénom(s) |
> |---|---|
> | SANKARA | Michail Alioun Juste |
> | KOANDA | Gildas |
> | BARRY | El Nour |
> | CONGO | Bénéré Nelson Cephas |
> | KONE | Assita |

## 1. Objectif

Exposer un **service SOAP** de gestion de clients dont la **base de référence est MongoDB**.
Les clients fictifs naissent dans **MySQL** ; **Airflow** les contrôle et les charge dans MongoDB ;
le service **Laravel** lit et modifie MongoDB ; les modifications sont **renvoyées vers MySQL** par un second DAG ;
**Zabbix** supervise l'ensemble.

## 2. Architecture

```mermaid
flowchart LR
  subgraph Source
    MY[(MySQL 8<br/>clients_src)]
  end
  subgraph Orchestration
    D1[DAG 1<br/>clients_mysql_to_mongo]
    D2[DAG 2<br/>clients_reconcile_mongo_to_mysql]
  end
  subgraph Reference
    MO[(MongoDB 7<br/>clients_db - BASE DE REFERENCE)]
  end
  SOAP[Laravel 12<br/>Service SOAP /soap/clients]
  CL[Client SOAP<br/>SoapUI / applications]
  ZB[Zabbix 7.0<br/>server + web + agent2]

  MY -->|extraction + contrôle qualité| D1 -->|upsert idempotent| MO
  MO -->|clients modifiés| D2 -->|UPDATE| MY
  CL -->|SOAP 1.1 / WSDL| SOAP <-->|lecture / écriture| MO
  ZB -.->|HTTP agent : /health, /monitoring/stats| SOAP
  ZB -.->|agent| ZB
```

| Composant | Rôle | Port hôte |
|---|---|---|
| `mysql` | Source : table `clients` (208 lignes fictives dont 7 invalides à dessein) | 3307 |
| `mongo` | **Base de référence** : `clients`, `clients_rejected`, `etl_runs`, `reconciliation_log`, `soap_calls` | 27018 |
| `airflow-*` | 2 DAG (`@hourly` et `30 * * * *`), LocalExecutor + PostgreSQL | 8081 |
| `laravel` | Service SOAP (ext-soap) + endpoints `/health` et `/monitoring/stats` | 8080 |
| `zabbix-*` | Serveur, interface web, agent 2 | 8082 |

## 3. Prérequis

- Docker ≥ 24 et Docker Compose v2 (`docker compose version`)
- ~6 Go de RAM libres, ports 3307, 8080, 8081, 8082, 10051, 27018 disponibles
- Python 3.9+ (uniquement pour les scripts de test et la configuration Zabbix, bibliothèque standard)
- Optionnel : SoapUI 5.7+ (tests manuels), PHP 8.3 avec `ext-soap` (tests sans Docker)

## 4. Installation (machine neuve)

```bash
git clone <URL-DU-DEPOT> soap-clients && cd soap-clients
cp .env.example .env            # optionnel : tous les paramètres ont une valeur par défaut
docker compose up -d --build    # 1er démarrage : 5 à 10 min (images + Laravel via Composer)
docker compose ps               # attendre que mysql, mongo, laravel soient « healthy »
```

Vérifications rapides :

| Quoi | Commande / URL | Attendu |
|---|---|---|
| WSDL | <http://localhost:8080/soap/clients?wsdl> | document XML `ClientService` |
| Santé | `curl localhost:8080/health` | `{"status":"ok","mongodb":"up"}` |
| Airflow | <http://localhost:8081> (admin / admin) | 2 DAG actifs |
| Zabbix | <http://localhost:8082> (Admin / zabbix) | assistant d'installation déjà fait par l'image |

### 4.1 Charger MongoDB (DAG 1)
Le DAG `clients_mysql_to_mongo` démarre automatiquement (non en pause). Pour ne pas attendre l'heure suivante :

```bash
docker compose exec airflow-scheduler airflow dags trigger clients_mysql_to_mongo
docker compose exec mongo mongosh "mongodb://app:app_password@localhost/clients_db?authSource=clients_db" \
  --eval 'printjson({clients: db.clients.countDocuments(), rejetes: db.clients_rejected.countDocuments()})'
```
Attendu : **201 clients** chargés, **7 rejetés** (motifs dans `clients_rejected`).

### 4.2 Configurer Zabbix (procédure distincte, outil à installation particulière)
```bash
python3 zabbix/setup_zabbix.py          # importe le template, crée l'hôte soap-clients-app
```
Détails et procédure manuelle : [`docs/SUPERVISION_ZABBIX.md`](docs/SUPERVISION_ZABBIX.md).

## 5. Utilisation du service SOAP

- **WSDL** : `http://localhost:8080/soap/clients?wsdl` — **Endpoint** : `POST http://localhost:8080/soap/clients`
- Opérations : `getClientDetails`, `searchClients`, `updateClient` (document/literal, SOAP 1.1)
- Documentation complète (paramètres, réponses, règles de validation, Faults) : [`docs/DOCUMENTATION_SOAP.md`](docs/DOCUMENTATION_SOAP.md)

Exemple :
```bash
curl -s -X POST http://localhost:8080/soap/clients -H 'Content-Type: text/xml' \
  --data @tests/soapui/requests/01_getClientDetails_ok.xml
```

## 6. Tests

| Niveau | Commande | Couvre |
|---|---|---|
| **Chaîne complète (Docker)** | `bash tests/e2e/run_pipeline_e2e.sh` | MySQL → DAG 1 → MongoDB → SOAP → DAG 2 → MySQL, idempotence, protection des modifications |
| **SOAP (Docker)** | `python3 tests/e2e/run_soap_tests.py --db-down docker` | WSDL, 3 opérations, codes de Fault, panne puis reprise de MongoDB |
| ETL + réconciliation | `pip install -r airflow/requirements-dev.txt && pytest airflow/tests -v` | 21 tests (qualité, idempotence, conflits, réconciliation) |
| SOAP sans Docker | `php -S 127.0.0.1:8099 tests/harness/server.php` puis `python3 tests/e2e/run_soap_tests.py --url http://127.0.0.1:8099 --db-down harness` | couche SOAP seule (dépôt en mémoire) |
| SoapUI | importer le WSDL, coller les requêtes de `tests/soapui/requests/` | voir [`docs/TESTS.md`](docs/TESTS.md) |

**Scénario de bout en bout (obligatoire)** : `docs/TESTS.md` §3 — modification SOAP → MongoDB → DAG 2 → MySQL, avec les résultats attendus.

## 7. Stratégie de réconciliation MongoDB → MySQL

MongoDB est la référence. `updateClient` marque le document (`locally_modified`, `sync_status=pending_mysql`, `version+1`) ;
le DAG 2 renvoie les champs vers MySQL, détecte les conflits (ligne MySQL modifiée entre-temps : **MongoDB l'emporte**, l'ancienne valeur est archivée),
et ne remet à zéro le drapeau que si aucune nouvelle modification n'est arrivée. Le DAG 1 ne réécrase **jamais** un client modifié côté Mongo.
Détails : [`docs/RECONCILIATION.md`](docs/RECONCILIATION.md).

## 8. Arborescence

```
docker-compose.yml        Pile complète (11 services)
docker/laravel.Dockerfile PHP 8.3 + ext-soap + ext-mongodb + Laravel 12
db/mysql, db/mongo        Schéma, jeu de données (générateur déterministe), init MongoDB (index, JSON Schema)
airflow/dags              2 DAG + package clients_etl (rules, etl, reconcile) ; airflow/tests = pytest
laravel-app/          Code du service (projet Laravel 12 complet, composer.lock inclus) : WSDL, SOAP, dépôt Mongo
zabbix/                   Template YAML + script de configuration par API
tests/                    e2e Python, requêtes SoapUI, serveur de test PHP
docs/                     Documentation SOAP, réconciliation, supervision, tests, résultats
presentation/             Présentation PowerPoint
```

## 9. État de validation (honnêteté technique)

| Élément | Validé comment |
|---|---|
| Couche SOAP (WSDL, 3 opérations, Faults, validation) | **Exécutée** : 20/20 tests e2e sur serveur PHP 8.3 + client `SoapClient` PHP — rapport `docs/RESULTATS_TESTS_HARNESS.md` |
| ETL, qualité, idempotence, réconciliation | **Exécutés** : 21 tests pytest (MongoDB simulé par `mongomock`) |
| DAG Airflow | **Importés** dans Airflow 2.9.3 réel, sans erreur ; graphe de tâches vérifié |
| `MongoClientRepository`, image Laravel, `docker-compose.yml` | **Validés sur pile Docker réelle** (octobre 2026) : 18/18 tests SOAP (`docs/RESULTATS_TESTS_DOCKER.md`), panne et reprise de MongoDB, scénario MySQL → Airflow → MongoDB → SOAP → Airflow → MySQL |
| Template Zabbix | **Importé dans Zabbix 7.0.32** via `zabbix/setup_zabbix.py` ; métriques reçues, alerte « MongoDB indisponible » testée |

### Dépannage probable au premier lancement
| Symptôme | Cause / action |
|---|---|
| Docker : « failed to connect to the docker API » / erreur 500 sur `_ping` | Docker Desktop n'est pas (encore) démarré : attendre « Engine running » ; sinon `wsl --update` puis `wsl --shutdown` et relancer Docker Desktop |
| Build `laravel` : Composer refuse `laravel/framework` (« security advisories ») | Version de Laravel hors support. Le Dockerfile utilise Laravel 12 ; ne pas désactiver `policy.advisories.block` |
| Build `laravel` : `mongodb/mongodb` incompatible avec `ext-mongodb` | Garder l'extension et la bibliothèque sur la même branche (1.21.x ↔ ^1.21) |
| `laravel` ne devient pas healthy | `docker compose logs laravel` ; vérifier la compilation de `pecl install mongodb-1.21.10` |
| WSDL OK mais Fault `SERVICE_UNAVAILABLE` | Mongo non prêt ou mot de passe `.env` différent de celui d'init (supprimer les volumes : `docker compose down -v`) |
| DAG absent dans Airflow | `docker compose exec airflow-scheduler airflow dags list-import-errors` |
| Import du template Zabbix refusé | Le message exact est affiché par `zabbix/setup_zabbix.py` (version Zabbix ≠ 7.0 : adapter `version:` ; format : `graphs` doit être au niveau de `zabbix_export`) |
| Journal Zabbix : `host [...] not found` | `ZBX_HOSTNAME` de l'agent doit être identique au nom de l'hôte (`soap-clients-app`) |


---

## Annexe A : Prérequis matériels et premier démarrage

- **Mémoire** : 8 Go de RAM minimum pour toute la pile (Airflow, Zabbix, MySQL ×2, MongoDB, PostgreSQL, Laravel). Sous Windows, Docker Desktop utilise WSL 2 : limiter sa mémoire à 6 Go dans `C:\Users\<utilisateur>\.wslconfig` (`[wsl2]` puis `memory=6GB`) si la machine ralentit.
- **Disque** : environ 10 Go (images Docker comprises).
- **Premier démarrage** : compter 10 à 20 minutes (téléchargement des images, initialisation d'Airflow, création de la base de Zabbix par `zabbix-server`).
- **Ne pas interrompre `docker compose up -d`** (fermeture du terminal, `Ctrl+C`) : des services peuvent rester à l'état `Created`. Dans ce cas, relancer simplement `docker compose up -d` (la commande est idempotente), puis vérifier `docker compose ps -a`.
- **Zabbix** : attendre que l'API réponde avant d'exécuter `zabbix/setup_zabbix.py` (la base de Zabbix est créée au premier démarrage, 5 à 10 minutes) :

```bash
for i in $(seq 1 60); do curl -s -X POST http://localhost:8082/api_jsonrpc.php -H "Content-Type: application/json-rpc" -d '{"jsonrpc":"2.0","method":"apiinfo.version","params":[],"id":1}' | grep -q '"result"' && { echo "Zabbix prêt"; break; }; echo "Zabbix pas encore prêt ($i/60)..."; sleep 15; done
```

## Annexe B : Lancer les scripts Python sans installer Python

Les scripts `zabbix/setup_zabbix.py` et `tests/e2e/run_soap_tests.py` n'utilisent que la bibliothèque standard. Si Python n'est pas installé, on les exécute dans un conteneur jetable, depuis la racine du dépôt.

**Git Bash (Windows)** :

```bash
# Import du template Zabbix et création de l'hôte
MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd -W):/w" -w /w \
  -e ZABBIX_URL=http://host.docker.internal:8082/api_jsonrpc.php \
  python:3.12-slim python zabbix/setup_zabbix.py

# Tests SOAP (sans le test de panne, qui nécessite le client Docker)
MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd -W):/w" -w /w python:3.12-slim \
  python tests/e2e/run_soap_tests.py --url http://host.docker.internal:8080 --db-down skip
```

**Linux / macOS** : remplacer `$(pwd -W)` par `$(pwd)`, supprimer `MSYS_NO_PATHCONV=1` et, sous Linux, ajouter `--add-host=host.docker.internal:host-gateway` à `docker run`.

Avec Python 3 installé localement : `python3 zabbix/setup_zabbix.py` et `python3 tests/e2e/run_soap_tests.py --db-down docker`.

## Annexe C : Procédure de recette (ordre conseillé)

1. `cp .env.example .env` puis `docker compose up -d --build` ; attendre 3 à 5 minutes puis vérifier `docker compose ps -a` (`airflow-init` terminé avec le code 0, les autres services `Up` ou `healthy`).
2. Attendre que Zabbix réponde (boucle de l'annexe A), puis exécuter `zabbix/setup_zabbix.py` (annexe B).
3. Test de bout en bout de la chaîne principale :
   `bash tests/e2e/run_pipeline_e2e.sh` : résultat attendu : **22 réussis, 0 échecs**.
4. Tests SOAP détaillés (annexe B) : résultat attendu : **18/18**.
5. Supervision : <http://localhost:8082> (`Admin` / `zabbix`), *Monitoring → Latest data*, hôte `soap-clients-app` : `soap.clients.total` = 201, `soap.mongodb.up` = 1. Simulation de panne : `docker compose stop mongo` (alerte « MongoDB indisponible » après environ 1 minute), puis `docker compose start mongo` (résolution automatique).
6. Nettoyage complet : `docker compose down -v`.
