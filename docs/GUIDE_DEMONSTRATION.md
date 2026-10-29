# Démonstration du projet — Groupe 5 SI

## 1. Préparer la séance

- Suivre l’installation du README depuis la racine du dépôt.
- Vérifier les services, charger les clients avec Airflow et configurer Zabbix.
- Ouvrir SoapUI, Airflow (`http://localhost:8081`) et Zabbix (`http://localhost:8082`).
- Conserver les résultats des tests dans les fichiers indiqués par [TESTS.md](TESTS.md).

Le jeu initial comporte 208 lignes MySQL. Le premier chargement doit produire
201 clients valides dans MongoDB et 7 rejets motivés. Les versions des fiches
peuvent être supérieures à 1 si les tests ont déjà été exécutés.

## 2. Fil conducteur de la présentation

| Étape | Action à montrer | Ce qu’il faut expliquer |
|---|---|---|
| 1 | Schéma de l’architecture | Rôle de chaque outil et référence MongoDB |
| 2 | Table MySQL et exemples de données invalides | Source initiale, données fictives |
| 3 | DAG `clients_mysql_to_mongo` réussi | Extraction, validation, chargement |
| 4 | Collections `clients` et `clients_rejected` | 201 fiches acceptées, 7 rejetées |
| 5 | Deuxième passage de l’import | Aucun doublon ; stabilité des fiches inchangées |
| 6 | WSDL dans SoapUI | Contrat des trois opérations |
| 7 | `getClientDetails` puis `searchClients` | Consultation, filtres et pagination |
| 8 | `updateClient` avec la version courante | Modification MongoDB, état `pending_mysql` |
| 9 | Valeur MySQL avant réconciliation | Cohérence différée entre les bases |
| 10 | DAG `clients_reconcile_mongo_to_mysql` | Retour vers MySQL et journal d’audit |
| 11 | Paramètre invalide et client absent | Fault métier structurée, HTTP 500 |
| 12 | Zabbix puis panne contrôlée | Détection de panne et rétablissement |

## 3. Explication à savoir donner

« Le programme consommateur envoie une demande SOAP en XML. Laravel la reçoit,
SoapServer identifie l’opération et notre code consulte ou modifie MongoDB.
La réponse suit le WSDL. Airflow gère les transferts de données et Zabbix
surveille le fonctionnement. »

Pour la réconciliation : « Une modification SOAP reste prioritaire. Un ancien
lot MySQL ne peut pas remettre l’ancienne valeur, même si le retour vers MySQL
a déjà eu lieu. »

## 4. Répartition de la parole

Les membres peuvent se répartir la présentation entre données, Airflow, SOAP,
tests et supervision. Chaque membre doit pouvoir expliquer le trajet complet
d’une requête et la raison du choix de MongoDB comme référence.

Le PowerPoint est dans [presentation](../presentation). Les noms des auteurs
doivent correspondre aux membres réels ; ne pas conserver d’identité fictive.

## 5. Remise

Le dépôt public doit contenir code, dépendances verrouillées, scripts des bases,
configurations, WSDL, documentation, tests, résultats réels et PowerPoint.
Le README doit permettre une installation sur une machine neuve.

D’après l’énoncé fourni : transmettre le lien du dépôt à
`kyfadeloumar@gmail.com`, avec l’objet `[PROJET_DEV_COMPOSANT_2026]`, en indiquant
Groupe 5 SI, Exercice 7 et les membres. La publication et l’envoi sont réalisés
par le groupe après relecture.
