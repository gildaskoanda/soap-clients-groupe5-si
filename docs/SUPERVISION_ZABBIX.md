# Supervision avec Zabbix

## 1. Objectif

Vérifier que le service répond, que MongoDB est accessible et que la chaîne
de données continue de fonctionner. La configuration est fournie par
[template_soap_clients.yaml](../zabbix/template_soap_clients.yaml).

## 2. Installation locale

L’environnement Docker comprend la base de Zabbix, le serveur, son interface web
et un agent. Après le démarrage décrit dans le README :

```sh
python3 zabbix/setup_zabbix.py
```

Le script attend l’API, importe le modèle, crée le groupe `SOAP Clients` et l’hôte
`soap-clients-app`. L’interface est accessible à `http://localhost:8082`.
Les identifiants initiaux de l’image officielle sont `Admin` / `zabbix`.

Pour un compte déjà personnalisé, fournir `ZABBIX_USER` et `ZABBIX_PASSWORD`
dans l’environnement du script. `ZABBIX_URL` permet de changer l’adresse de l’API.
Ne pas inscrire de véritables mots de passe dans les fichiers du dépôt.

Le nom d’hôte de l’agent doit correspondre à `soap-clients-app`. Depuis Zabbix,
Laravel est joignable par `http://laravel`, et non par `localhost:8080`.

## 3. Contrôles et alertes

| Contrôle | Collecte ou seuil |
|---|---|
| `/health` | Toutes les 30 secondes ; HTTP 200 ou 503 accepté pour analyser la réponse |
| Service injoignable | Absence de réponse pendant 2 minutes |
| MongoDB indisponible | Valeur `mongodb` différente de `up` |
| `/monitoring/stats` | Toutes les minutes ; statistiques des 5 dernières minutes |
| Erreurs serveur SOAP | Au moins 3 erreurs sur la fenêtre de 5 minutes |
| Latence moyenne | Seuil configurable, 500 ms par défaut |
| Import Airflow trop ancien | Plus de 7 200 secondes depuis le dernier import terminé |
| Attente de réconciliation | Plus de 50 fiches en attente |
| Appel SOAP de contrôle | Lecture périodique du client `CLI-000010` |
| Contrat WSDL | Toutes les minutes ; exactement trois opérations attendues |

Les seuils sont des macros du modèle et peuvent être adaptés à la démonstration.
Le modèle comporte 14 éléments, 8 déclencheurs et 2 graphiques. Le contrôle SOAP
déclenche une alerte après trois échecs consécutifs, ou sans donnée pendant
3 minutes ; le contrôle WSDL signale un nombre d’opérations différent de trois.
Les erreurs de validation métier sont comptées séparément des erreurs techniques.
La latence moyenne et l’âge ETL sont de type numérique flottant : cela préserve
les décimales et permet la valeur `-1` signifiant « jamais exécuté ». Les autres
compteurs sont des entiers positifs.

Le journal `soap_calls` est stocké dans MongoDB. Quand MongoDB est arrêté, les
nouveaux appels ne peuvent pas y être enregistrés ; le contrôle `/health` et
l’appel SOAP de contrôle restent donc nécessaires pour détecter cette panne.
La route `/up` de Laravel, seule, ne valide pas le service SOAP.

## 4. Vérification dans l’interface

1. Ouvrir **Monitoring → Latest data** et sélectionner `soap-clients-app`.
2. Vérifier les valeurs de santé, le nombre de clients et les statistiques SOAP.
3. Exécuter des requêtes SOAP et attendre le cycle de collecte suivant.
4. Ouvrir **Monitoring → Problems** pour voir les alertes.
5. Consulter les graphiques des appels, des erreurs et de la latence.

Si l’import automatique échoue, lire le message retourné par le script. Une
procédure manuelle équivalente consiste à importer le YAML dans **Data collection
→ Templates**, créer l’hôte avec l’interface agent `zabbix-agent:10050`, puis
lui associer `SOAP Clients Service` et `Linux by Zabbix agent`.

## 5. Panne contrôlée de démonstration

Sur l’environnement de démonstration uniquement, arrêter MongoDB puis rejouer
une consultation SOAP :

```sh
docker compose stop mongo
```

Résultats attendus : `/health` renvoie 503, la consultation produit
`SERVICE_UNAVAILABLE` et Zabbix signale l’indisponibilité. Remettre ensuite la base
en service et vérifier le rétablissement :

```sh
docker compose start mongo
```

Le script de tests SOAP sait aussi réaliser ce scénario avec restauration de la
base. Pour démontrer une panne de Laravel, arrêter puis redémarrer uniquement le
service `laravel` et attendre le délai de l’alerte d’absence de réponse.

Joindre au compte rendu une capture de l’état normal, de l’alerte et du retour
à la normale. Aucune notification par courriel n’est configurée : les alertes
sont visibles dans Zabbix.

## 6. Test automatisé de supervision

Après l’import du modèle et le chargement des clients :

```sh
python3 tests/e2e/run_zabbix_tests.py --simulate-outage
```

Le script attend la collecte, vérifie les 14 éléments, le WSDL et une consultation
SOAP, arrête MongoDB, attend l’alerte, redémarre la base et vérifie la résolution.
Les événements sont conservés dans [RESULTATS_ZABBIX.md](RESULTATS_ZABBIX.md).
Sans `--simulate-outage`, seuls les contrôles de lecture sont exécutés.

Ne pas lancer ce scénario en même temps que les autres tests. En cas d’arrêt
brutal du processus, vérifier `docker compose ps` et remettre MongoDB en service
avec `docker compose start mongo` si nécessaire.

Références des contrôles : [types de mesures Zabbix](https://www.zabbix.com/documentation/7.0/en/manual/api/reference/item/object)
et [lecture des événements](https://www.zabbix.com/documentation/7.0/en/manual/api/reference/event/get).
