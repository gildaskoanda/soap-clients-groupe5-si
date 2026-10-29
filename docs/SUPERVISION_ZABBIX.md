# Supervision Zabbix

## Architecture de supervision
Le serveur Zabbix interroge deux endpoints du service Laravel (**agent HTTP**, sans agent installé sur l'application) :

| Endpoint | Contenu | Fréquence |
|---|---|---|
| `GET /health` | 200 `{"status":"ok","mongodb":"up"}` ou 503 si MongoDB est injoignable | 30 s |
| `GET /monitoring/stats` | JSON : appels, fautes, fautes serveur, latences moyenne/max (fenêtre 5 min), nombre de clients, clients en attente de réconciliation, âge et rejets du dernier ETL | 1 min |

L'**agent Zabbix 2** (conteneur `zabbix-agent`) fournit les métriques système via le template *Linux by Zabbix agent*.

## Mise en route
1. `docker compose up -d` (les services `zabbix-*` démarrent avec la pile).
2. `python3 zabbix/setup_zabbix.py` : importe le template, crée le groupe `SOAP Clients` et l'hôte `soap-clients-app`.
3. Interface : <http://localhost:8082> — compte par défaut `Admin` / `zabbix` (**à changer** immédiatement).
4. *Monitoring → Latest data* → filtrer sur l'hôte `soap-clients-app`. Premières valeurs sous 1 à 2 minutes.

### Procédure manuelle (si le script échoue)
*Data collection → Templates → Import* → `zabbix/template_soap_clients.yaml` ; *Hosts → Create host* : nom `soap-clients-app`, groupe `SOAP Clients`, interface Agent DNS `zabbix-agent` port 10050, templates `SOAP Clients Service` et `Linux by Zabbix agent`.

## Éléments du template « SOAP Clients Service »
| Élément | Clé | Alerte |
|---|---|---|
| Santé (brut) | `soap.health.raw` | **HIGH** : aucune réponse depuis 2 min |
| MongoDB joignable | `soap.mongodb.up` | **HIGH** : valeur 0 |
| Appels SOAP (5 min) | `soap.calls.5m` | — |
| Fautes SOAP (5 min) | `soap.faults.5m` | — (les fautes métier sont normales) |
| Fautes serveur (5 min) | `soap.faults.server.5m` | AVERAGE : ≥ 3 |
| Latence moyenne / max | `soap.latency.avg` / `.max` | WARNING : moyenne > `{$SOAP_LATENCY_WARN_MS}` (500 ms) |
| Clients en base de référence | `soap.clients.total` | — |
| Clients en attente de réconciliation | `soap.reconciliation.pending` | WARNING : > `{$PENDING_RECONCILIATION_WARN}` (50) |
| Âge du dernier ETL | `soap.etl.age` | WARNING : > `{$ETL_MAX_AGE_SEC}` (2 h) ou jamais exécuté |
| Lignes rejetées (dernier ETL) | `soap.etl.rejected` | — |

Deux graphiques : *Appels et fautes SOAP*, *Latence SOAP*. Les seuils sont des macros modifiables par hôte.

## Scénarios de démonstration
| Action | Effet attendu dans Zabbix |
|---|---|
| Lancer `tests/e2e/run_soap_tests.py` | pic d'appels et de fautes (métier) sur le graphique |
| `docker compose stop mongo` | en < 1 min : `soap.mongodb.up = 0` → problème **HIGH** « MongoDB indisponible » ; fautes serveur ≥ 3 si des appels continuent |
| `docker compose start mongo` | le problème se résout seul |
| `docker compose stop laravel` | problème **HIGH** « Service SOAP injoignable » après 2 min |
| Modifier 2 clients puis attendre | `soap.reconciliation.pending = 2`, retombe à 0 après le DAG 2 |

## Limites
- Les métriques de latence sont calculées côté service (durée de traitement PHP), pas côté réseau.
- Pas de notification (e-mail/Telegram) configurée : à ajouter dans *Alerts → Media types* si besoin.
- Template écrit pour **Zabbix 7.0 LTS** ; en 6.x certains champs YAML diffèrent.
