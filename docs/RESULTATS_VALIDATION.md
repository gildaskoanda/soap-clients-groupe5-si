# Résultats de validation — Groupe 5 SI

Vérifications réalisées les **28 et 29 octobre 2026 (UTC)** sur la pile locale.
L’initialisation des bases a été exécutée le 29 octobre avec autorisation du
responsable. Les rapports ci-dessous distinguent simulations et services réels.

## 1. Bilan vérifié

| Contrôle exécuté | Résultat | Portée exacte |
|---|---|---|
| Tests Python ETL et réconciliation | **33/33 réussis** | Bases simulées ; Python 3.12.3, pytest 9.2.0 |
| Couverture Python | **98 %** | 173 instructions, 3 non couvertes ; seulement `clients_etl` |
| Tests SOAP sur serveur isolé | **23/23 réussis** | Vrai moteur PHP SOAP, dépôt en mémoire, panne simulée |
| Tests SOAP sur pile Docker réelle | **23/23 réussis** | Laravel et MongoDB réels, arrêt et redémarrage de MongoDB inclus |
| Chaîne complète | **27/27 contrôles réussis** | MySQL → Airflow → MongoDB → SOAP → Airflow → MySQL |
| Supervision réelle | **9/9 contrôles réussis** | Zabbix 7.0.32, alerte MongoDB observée puis résolue |
| Construction Docker Laravel | Réussie | PHP 8.3.36, Laravel 12.70.1, extension MongoDB 1.21.10 |
| Construction Docker Airflow | Réussie | Airflow 2.9.3 / Python 3.11, PyMySQL 1.1.1, PyMongo 4.8.0 |
| Airflow | **2 DAG, 4 tâches, aucune erreur d’import** | Import isolé puis exécutions réelles réussies des deux DAG |
| Composer | Configuration et plateforme valides | Dépendances de production installées depuis le verrou |
| Audit Composer après correction | Aucun avis de vulnérabilité connu signalé | Dépendances PHP ; ce n’est pas un audit complet des images |
| Syntaxe PHP | Valide | Classes applicatives et routes |
| Caches Laravel | Réussis | Configuration, routes et vues |
| Démarrage HTTP Laravel sans MongoDB | **4 contrôles réussis** | Accueil 200, WSDL 200, santé 503, Fault `SERVICE_UNAVAILABLE` 500 |
| Docker Compose | 11 services initialisés | Dix services persistants ; `airflow-init` terminé avec code 0 |
| Données réelles | **208 / 201 / 7** | Lignes MySQL / clients MongoDB / rejets de qualité |
| Modèle Zabbix | 14 éléments, 8 déclencheurs, 2 graphiques | Importé deux fois sans doublon ; collecte réelle vérifiée |
| Présentation | 13 diapositives, noms renseignés | Conversion PDF et contrôle visuel des diapositives modifiées |

Les détails des tests sont conservés dans
[RESULTATS_PYTEST.txt](RESULTATS_PYTEST.txt) et
[RESULTATS_TESTS_HARNESS.md](RESULTATS_TESTS_HARNESS.md), ainsi que
[RESULTATS_TESTS_DOCKER.md](RESULTATS_TESTS_DOCKER.md),
[RESULTATS_PIPELINE.txt](RESULTATS_PIPELINE.txt) et
[RESULTATS_ZABBIX.md](RESULTATS_ZABBIX.md).

## 2. Corrections démontrées par les vérifications

1. **Ancien lot MySQL** : un lot extrait avant une modification SOAP pouvait
   réécraser celle-ci après sa réconciliation. La propriété SOAP est désormais
   conservée et contrôlée pendant l’import ; une comparaison atomique protège
   également les écritures concurrentes.
2. **Compteurs ETL** : une mise à jour concurrente non effectuée pouvait être
   comptée comme réussie. Les compteurs utilisent maintenant le résultat réel
   de l’écriture. Quatre cas de régression ont échoué avant la correction,
   puis réussi après celle-ci.
3. **Réconciliation** : verrouillage de la ligne MySQL, journalisation avant
   acquittement et contrôle de version empêchant d’acquitter une nouvelle
   modification SOAP à la place de l’ancienne.
4. **Découverte Airflow** : l’analyse de `clients_etl/etl.py` comme fichier DAG
   produisait `ImportError: attempted relative import with no known parent
   package`. Les deux vrais DAG s’importaient déjà : le paquet n’était donc
   pas absent. `.airflowignore` exclut les utilitaires de la découverte et le
   contrôle ne remonte plus aucune erreur.
5. **Dépendance PHP** : Composer signalait l’avis `PKSA-wtxr-p26d-nn42` pour
   `symfony/mime` 7.4.19. Mise à jour ciblée vers 7.4.22 ; les autres versions
   sont conservées. Le nouvel audit ne signale aucun avis connu.
6. **Configuration locale** : secrets générés sans écrasement de `.env`, ports
   limités à la machine locale, extensions PHP requises et pilotes Laravel
   sans dépendance à des tables SQLite inexistantes.
7. **Types Zabbix** : le contrôle Z03 a échoué car la latence moyenne et l’âge
   ETL étaient des entiers non signés. Le type flottant préserve les décimales
   et autorise la sentinelle `-1` ; après réimport, les neuf contrôles passent.

## 3. Preuve de panne et de rétablissement

MongoDB a réellement été arrêté, puis remis en service par le test. Le service
a répondu par une Fault HTTP 500 `SERVICE_UNAVAILABLE`, puis de nouveau par une
consultation HTTP 200. Zabbix a enregistré les événements locaux suivants :

| Événement | Horodatage Unix | État |
|---|---|---|
| 37 | 1793233028 | MongoDB indisponible, problème actif |
| 38 | 1793233056 | Rétablissement, problème résolu |

La collecte finale indique `soap.mongodb.up=1`, `soap.check.ok=1`,
`soap.wsdl.operations=3` et `soap.clients.total=201`.

Ces événements prouvent l’alerte MongoDB, pas le déclenchement artificiel des huit
alertes du modèle. Les autres seuils sont configurés, mais n’ont pas tous fait
l’objet d’une panne ou d’une charge provoquée.

## 4. Reproduire et préparer la soutenance

Les commandes détaillées figurent dans [TESTS.md](TESTS.md), l’installation dans
le [README](../README.md) et la supervision dans
[SUPERVISION_ZABBIX.md](SUPERVISION_ZABBIX.md).

Les essais ont été réalisés sous Linux avec Docker. Les requêtes SOAP ont été
exécutées automatiquement, pas dans l’application graphique SoapUI. Préparer
encore la démonstration manuelle et les captures d’écran de l’interface pour la
soutenance. Aucun test Windows ou macOS n’est revendiqué.

Les services sont laissés en fonctionnement local avec leurs volumes. Les
fiches utilisées par les tests sont fictives et leurs versions ont augmenté.
Ne pas publier `.env` ni des identifiants de connexion.

PHPStan, Pint, PHPUnit et un audit complet des images système n’ont pas été
exécutés. Le contrôle du contrat SOAP, des régressions, de la couverture, des
dépendances et des caches ne remplace pas ces vérifications complémentaires.
