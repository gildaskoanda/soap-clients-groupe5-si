# Plan de tests reproductibles

Les résultats réellement obtenus figurent dans [RESULTATS_VALIDATION.md](RESULTATS_VALIDATION.md).
Les nombres et états ci-dessous sont des **attendus**, pas une preuve d’exécution.

## 1. Niveaux de vérification

| Niveau | Fichier | Ce qu’il vérifie | Limite |
|---|---|---|---|
| Logique Python | `airflow/tests/test_etl.py` | 33 cas de qualité, import, concurrence et réconciliation | MySQL et MongoDB simulés |
| SOAP isolé | `tests/e2e/run_soap_tests.py` + `tests/harness/` | 23 cas, WSDL, opérations, Faults et panne simulée | Pas de Laravel HTTP complet ni de base réelle |
| SOAP réel | `tests/e2e/run_soap_tests.py --db-down docker` | Les mêmes 23 cas sur Laravel et MongoDB | Modifie un client fictif et coupe brièvement MongoDB |
| Chaîne complète | `tests/e2e/run_pipeline_e2e.sh` | MySQL → Airflow → MongoDB → SOAP → Airflow → MySQL | Nécessite toute la pile et les DAG disponibles |
| Supervision | Modèle Zabbix et interface web | Collecte, alerte et rétablissement | Nécessite un import et des cycles de collecte réels |
| Supervision automatisée | `tests/e2e/run_zabbix_tests.py --simulate-outage` | Neuf contrôles, dont panne réelle et résolution | Coupe uniquement MongoDB local ; à exécuter séparément |

## 2. Tests Python, sans bases

Depuis la racine du dépôt :

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r airflow/requirements-dev.txt
.venv/bin/python -m pytest airflow/tests -v --cov=airflow/dags/clients_etl --cov-report=term-missing
```

Les régressions incluent un lot MySQL extrait avant une modification SOAP déjà
réconciliée, une écriture SOAP concurrente, le comptage des écritures réellement
effectuées, les collisions d’e-mail, une erreur technique et l’échec du journal.
Une couverture élevée de ces modules ne mesure pas la couverture de toute la pile.

### Découverte des DAG, sans base de métadonnées

Après construction de l’image Airflow, sous Linux ou macOS :

```sh
docker run --rm --network none --entrypoint python \
  -e PYTHONPATH=/opt/airflow/dags \
  --mount "type=bind,source=$PWD/airflow/dags,target=/opt/airflow/dags,readonly" \
  --mount "type=bind,source=$PWD/scripts/verifier_dags.py,target=/tmp/verifier_dags.py,readonly" \
  soap-clients-groupe5-si-airflow:local /tmp/verifier_dags.py
```

Attendu : deux DAG, quatre tâches et aucune erreur d’import. Le fichier
`.airflowignore` exclut le dossier utilitaire de la recherche de DAG, mais
n’empêche pas les imports Python de ses modules.

## 3. SOAP isolé, sans bases

Prérequis : PHP 8.3 avec les extensions `soap` et `mbstring`.
Dans un premier terminal :

```sh
php -S 127.0.0.1:8099 tests/harness/server.php
```

Dans un second terminal :

```sh
python3 tests/e2e/run_soap_tests.py --url http://127.0.0.1:8099 --db-down harness --report docs/RESULTATS_TESTS_HARNESS.md
```

Le dépôt de test est réinitialisé au début. Ses routes `/_test/*` ne sont pas
exposées par Laravel. Ne pas publier ce serveur de test sur un réseau public.

## 4. SOAP sur Laravel et MongoDB réels

Initialiser l’environnement avec le responsable du projet, suivre le README,
puis exécuter le DAG d’import jusqu’à son succès. Avant les tests, mettre le DAG
de réconciliation en pause dans Airflow et attendre la fin de ses éventuelles
exécutions actives. Cela permet d’observer l’état `pending_mysql` sans course
avec le retour MySQL. Rétablir ensuite son état de pause initial.

```sh
python3 tests/e2e/run_soap_tests.py --db-down docker --report docs/RESULTATS_TESTS_DOCKER.md
```

Le script arrête **uniquement MongoDB de ce projet**, puis tente systématiquement
de le redémarrer. Ne pas l’exécuter sur un environnement partagé ou de production.
Si le processus est interrompu brutalement, vérifier `docker compose ps` et
relancer `docker compose start mongo` si nécessaire.

Avec `--db-down skip`, 21 cas sont exécutés : la panne et la reprise ne sont
alors pas validées.

| Cas | Résultat attendu |
|---|---|
| T01 | WSDL accessible avec les trois opérations et l’adresse résolue |
| T02–T04 | Consultation valide, client absent, code mal formé |
| T05–T09 | Recherche, pagination, filtres invalides, résultat vide |
| T10–T12 | Modification persistée, version incrémentée, conflit détecté |
| T13–T17 | E-mail invalide ou utilisé, modification vide, client absent, téléphone invalide |
| T18 | Enveloppe incorrecte : Fault de protocole |
| T19–T20 | MongoDB indisponible : Fault serveur ; retour de la base : succès |
| T21–T23 | Enveloppe vide, page zéro et caractères spéciaux XML |

## 5. Chaîne complète

```sh
bash tests/e2e/run_pipeline_e2e.sh
```

Le scénario utilise `CLI-000020`, une ville nouvelle à chaque passage et conserve
l’état initial de pause du DAG de réconciliation. Il vérifie le chargement,
l’idempotence, l’écriture SOAP exclusivement dans MongoDB, sa protection contre
un nouvel import et le retour vers MySQL avec journalisation.
Il comporte 27 contrôles. Le dernier import vérifie que la protection SOAP
persiste après la réconciliation. Résultats observés :
[RESULTATS_PIPELINE.txt](RESULTATS_PIPELINE.txt).

Sur des volumes neufs, contrôler **208 lignes source, 201 clients valides et
7 rejets**. Après des tests de modification, les fiches gérées par SOAP peuvent
être comptées comme conflits ignorés ; ne plus attendre 201 fiches inchangées.

Pour tester un conflit métier, modifier une même fiche fictive côté MySQL et
côté SOAP, puis lancer la réconciliation : MongoDB doit l’emporter et le journal
doit conserver la ligne MySQL écrasée. Ne pas utiliser de données personnelles.

## 6. SoapUI et Zabbix

Importer `http://localhost:8080/soap/clients?wsdl` dans SoapUI, puis utiliser les
11 requêtes de [tests/soapui/requests](../tests/soapui/requests).
Le champ `versionAttendue` des exemples doit être adapté à la version relue.

Ajouter des assertions `SOAP Response`, `Not SOAP Fault` ou `SOAP Fault`, et
vérifier le code métier dans `detail/ClientFault/code`. Un préfixe XML (`ns1`,
`c`, etc.) n’est pas un identifiant stable : utiliser les espaces de noms.

Suivre le [guide Zabbix](SUPERVISION_ZABBIX.md) pour vérifier les valeurs
collectées, provoquer une panne contrôlée et capturer l’alerte puis la reprise.
Ne déclarer ces étapes réussies qu’après observation effective.

Le test automatisé Zabbix peut également être lancé après import du modèle :

```sh
python3 tests/e2e/run_zabbix_tests.py --simulate-outage
```

Il produit [RESULTATS_ZABBIX.md](RESULTATS_ZABBIX.md), avec les identifiants et
horodatages des événements de panne et de résolution. Les tests SOAP, de chaîne
complète et de supervision doivent être exécutés successivement.
