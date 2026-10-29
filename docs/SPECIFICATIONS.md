# Spécifications et décisions du projet

## 1. Besoin — PRD

Le groupe 5 SI doit démontrer un service SOAP de gestion de clients, alimenté
depuis MySQL par Airflow, utilisant MongoDB comme référence et supervisé par
Zabbix. Les utilisateurs sont les membres du groupe et l’enseignant, dans un
environnement local contenant exclusivement des données fictives.

Le périmètre correspond aux sept points de l’exercice 7. Il ne comprend pas
une application commerciale, une authentification SOAP, un hébergement public,
ni des opérations de création ou suppression de clients.

## 2. Exigences — SRS

| ID | Exigence | Critère de réception |
|---|---|---|
| F1 | Préparer MySQL | 208 lignes fictives, dont 7 invalides à dessein |
| F2 | Importer avec Airflow | 201 fiches valides, 7 rejets tracés, relance sans doublon |
| F3 | Exposer les trois opérations SOAP | WSDL chargeable ; lecture, recherche et modification testables |
| F4 | Décrire le contrat | Paramètres, structures, validations et Faults documentés |
| F5 | Prendre MongoDB pour référence | Les appels SOAP ne lisent et n’écrivent que MongoDB |
| F6 | Superviser et tester | Contrôles de santé, du WSDL et d’une requête SOAP ; tests reproductibles |
| F7 | Prévoir le retour vers MySQL | Réconciliation, conflits, reprises et limites documentés |

Exigences transversales : secrets locaux non versionnés, ports publiés sur
`127.0.0.1`, absence de détails sensibles dans les Faults, documentation des
limites et séparation des résultats obtenus et attendus.

## 3. Contrat

Le [WSDL](../laravel-app/resources/wsdl/clients.wsdl) définit les opérations,
messages et types XML. La [documentation SOAP](DOCUMENTATION_SOAP.md) en donne
la lecture humaine. Les changements conservent les noms et structures existants.

## 4. Architecture

- MySQL est la source initiale des clients.
- Airflow effectue le contrôle qualité et le chargement vers MongoDB.
- Laravel reçoit l’enveloppe HTTP, puis PHP `SoapServer` exécute l’opération.
- Le dépôt MongoDB isole les accès aux données du service métier.
- Un second DAG réconcilie les modifications SOAP vers MySQL.
- Zabbix interroge Laravel et surveille les métriques de fonctionnement.

Le schéma général figure dans le [README](../README.md).

## 5. Modélisation et décisions

L’identifiant métier stable est `code_client` (`codeClient` en XML). Les noms
de champs XML restent compatibles avec le WSDL existant. Les collections MongoDB
sont `clients`, `clients_rejected`, `etl_runs`, `reconciliation_log` et `soap_calls`.
Leurs contraintes sont définies dans [init.js](../db/mongo/init.js).

Une fiche importée commence à `version=1`, `source=mysql`, `sync_status=synced`.
Une modification SOAP incrémente sa version, fixe `source=soap` et la place en
attente (`locally_modified=true`, `sync_status=pending_mysql`). Le retour MySQL
ne l’acquitte que si sa version est restée inchangée.

La propriété `source=soap` est conservée après réconciliation : cela évite qu’un
ancien lot MySQL rétablisse une valeur périmée. En contrepartie, une fiche passée
sous gestion SOAP n’est plus actualisée par l’import MySQL. Cette décision est
détaillée dans [RECONCILIATION.md](RECONCILIATION.md).

Les écritures MongoDB utilisent une comparaison de version ; la réconciliation
verrouille la ligne MySQL pendant sa transaction. Il n’existe pas de transaction
distribuée entre les deux bases : le journal et les reprises rendent les écarts
détectables, sans promettre une synchronisation instantanée.

## 6. Vérification et livraison

Le [plan de tests](TESTS.md) couvre les exigences ci-dessus. Le
[rapport de validation](RESULTATS_VALIDATION.md) est la référence pour ce qui a
réellement été vérifié. Les initialisations de bases doivent être exécutées par
le responsable du projet, sauf autorisation explicite pour cet environnement.
