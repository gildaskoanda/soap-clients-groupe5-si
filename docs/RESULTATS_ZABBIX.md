# Résultats des tests Zabbix

Exécution UTC : 2026-10-29T00:17:39.014866+00:00

Panne réelle autorisée : True

| Contrôle | Résultat |
|---|---|
| Z01 API Zabbix 7.0 accessible | PASS |
| Z02 les 14 indicateurs sont supportés et récents | PASS |
| Z03 décimales et sentinelle négative représentables | PASS |
| Z04 consultation SOAP, WSDL et données corrects | PASS |
| Z05 panne réelle : Fault SERVICE_UNAVAILABLE | PASS |
| Z06 Zabbix détecte la panne réelle | PASS |
| Z07 consultation SOAP rétablie | PASS |
| Z08 Zabbix constate le retour à la normale | PASS |
| Z09 événements de panne et de reprise enregistrés | PASS |

**Bilan : 9/9 contrôles réussis.**

Les identifiants ci-dessous désignent les événements locaux, sans secret de connexion.

```json
{
  "version_zabbix": "7.0.32",
  "collecte_initiale": {
    "soap.calls.5m": {
      "itemid": "50801",
      "key_": "soap.calls.5m",
      "value_type": "3",
      "state": "0",
      "error": "",
      "lastclock": "1793232997",
      "lastvalue": "27"
    },
    "soap.check.ok": {
      "itemid": "50795",
      "key_": "soap.check.ok",
      "value_type": "3",
      "state": "0",
      "error": "",
      "lastclock": "1793232995",
      "lastvalue": "1"
    },
    "soap.clients.total": {
      "itemid": "50802",
      "key_": "soap.clients.total",
      "value_type": "3",
      "state": "0",
      "error": "",
      "lastclock": "1793232997",
      "lastvalue": "201"
    },
    "soap.etl.age": {
      "itemid": "50803",
      "key_": "soap.etl.age",
      "value_type": "0",
      "state": "0",
      "error": "",
      "lastclock": "1793232997",
      "lastvalue": "287"
    },
    "soap.etl.rejected": {
      "itemid": "50804",
      "key_": "soap.etl.rejected",
      "value_type": "3",
      "state": "0",
      "error": "",
      "lastclock": "1793232997",
      "lastvalue": "7"
    },
    "soap.faults.5m": {
      "itemid": "50805",
      "key_": "soap.faults.5m",
      "value_type": "3",
      "state": "0",
      "error": "",
      "lastclock": "1793232997",
      "lastvalue": "11"
    },
    "soap.faults.server.5m": {
      "itemid": "50806",
      "key_": "soap.faults.server.5m",
      "value_type": "3",
      "state": "0",
      "error": "",
      "lastclock": "1793232997",
      "lastvalue": "0"
    },
    "soap.health.raw": {
      "itemid": "50796",
      "key_": "soap.health.raw",
      "value_type": "4",
      "state": "0",
      "error": "",
      "lastclock": "1793232996",
      "lastvalue": "{\"status\":\"ok\",\"mongodb\":\"up\"}"
    },
    "soap.latency.avg": {
      "itemid": "50807",
      "key_": "soap.latency.avg",
      "value_type": "0",
      "state": "0",
      "error": "",
      "lastclock": "1793232997",
      "lastvalue": "0.8"
    },
    "soap.latency.max": {
      "itemid": "50808",
      "key_": "soap.latency.max",
      "value_type": "3",
      "state": "0",
      "error": "",
      "lastclock": "1793232997",
      "lastvalue": "5"
    },
    "soap.mongodb.up": {
      "itemid": "50810",
      "key_": "soap.mongodb.up",
      "value_type": "3",
      "state": "0",
      "error": "",
      "lastclock": "1793232996",
      "lastvalue": "1"
    },
    "soap.reconciliation.pending": {
      "itemid": "50809",
      "key_": "soap.reconciliation.pending",
      "value_type": "3",
      "state": "0",
      "error": "",
      "lastclock": "1793232997",
      "lastvalue": "1"
    },
    "soap.stats.raw": {
      "itemid": "50797",
      "key_": "soap.stats.raw",
      "value_type": "4",
      "state": "0",
      "error": "",
      "lastclock": "1793232997",
      "lastvalue": "{\"window_seconds\":300,\"calls\":27,\"faults\":11,\"server_faults\":0,\"avg_ms\":0.8,\"max_ms\":5,\"clients_total\":201,\"pending_reconciliation\":1,\"etl_last_status\":\"success_with_rejects\",\"etl_last_age_seconds\":287,\"etl_last_rejected\":7}"
    },
    "soap.wsdl.operations": {
      "itemid": "50798",
      "key_": "soap.wsdl.operations",
      "value_type": "3",
      "state": "0",
      "error": "",
      "lastclock": "1793232998",
      "lastvalue": "3"
    }
  },
  "alerte": {
    "triggerid": "25255",
    "description": "MongoDB indisponible pour le service SOAP",
    "value": "1",
    "lastchange": "1793233028"
  },
  "retablissement": {
    "triggerid": "25255",
    "description": "MongoDB indisponible pour le service SOAP",
    "value": "0",
    "lastchange": "1793233056"
  },
  "evenements": [
    {
      "eventid": "37",
      "clock": "1793233028",
      "value": "1",
      "name": "MongoDB indisponible pour le service SOAP"
    },
    {
      "eventid": "38",
      "clock": "1793233056",
      "value": "0",
      "name": "MongoDB indisponible pour le service SOAP"
    }
  ],
  "collecte_finale": {
    "soap.calls.5m": {
      "itemid": "50801",
      "key_": "soap.calls.5m",
      "value_type": "3",
      "state": "0",
      "error": "",
      "lastclock": "1793233057",
      "lastvalue": "27"
    },
    "soap.check.ok": {
      "itemid": "50795",
      "key_": "soap.check.ok",
      "value_type": "3",
      "state": "0",
      "error": "",
      "lastclock": "1793233055",
      "lastvalue": "1"
    },
    "soap.clients.total": {
      "itemid": "50802",
      "key_": "soap.clients.total",
      "value_type": "3",
      "state": "0",
      "error": "",
      "lastclock": "1793233057",
      "lastvalue": "201"
    },
    "soap.etl.age": {
      "itemid": "50803",
      "key_": "soap.etl.age",
      "value_type": "0",
      "state": "0",
      "error": "",
      "lastclock": "1793233057",
      "lastvalue": "347"
    },
    "soap.etl.rejected": {
      "itemid": "50804",
      "key_": "soap.etl.rejected",
      "value_type": "3",
      "state": "0",
      "error": "",
      "lastclock": "1793233057",
      "lastvalue": "7"
    },
    "soap.faults.5m": {
      "itemid": "50805",
      "key_": "soap.faults.5m",
      "value_type": "3",
      "state": "0",
      "error": "",
      "lastclock": "1793233057",
      "lastvalue": "11"
    },
    "soap.faults.server.5m": {
      "itemid": "50806",
      "key_": "soap.faults.server.5m",
      "value_type": "3",
      "state": "0",
      "error": "",
      "lastclock": "1793233057",
      "lastvalue": "0"
    },
    "soap.health.raw": {
      "itemid": "50796",
      "key_": "soap.health.raw",
      "value_type": "4",
      "state": "0",
      "error": "",
      "lastclock": "1793233056",
      "lastvalue": "{\"status\":\"ok\",\"mongodb\":\"up\"}"
    },
    "soap.latency.avg": {
      "itemid": "50807",
      "key_": "soap.latency.avg",
      "value_type": "0",
      "state": "0",
      "error": "",
      "lastclock": "1793233057",
      "lastvalue": "1.2"
    },
    "soap.latency.max": {
      "itemid": "50808",
      "key_": "soap.latency.max",
      "value_type": "3",
      "state": "0",
      "error": "",
      "lastclock": "1793233057",
      "lastvalue": "12"
    },
    "soap.mongodb.up": {
      "itemid": "50810",
      "key_": "soap.mongodb.up",
      "value_type": "3",
      "state": "0",
      "error": "",
      "lastclock": "1793233056",
      "lastvalue": "1"
    },
    "soap.reconciliation.pending": {
      "itemid": "50809",
      "key_": "soap.reconciliation.pending",
      "value_type": "3",
      "state": "0",
      "error": "",
      "lastclock": "1793233057",
      "lastvalue": "1"
    },
    "soap.stats.raw": {
      "itemid": "50797",
      "key_": "soap.stats.raw",
      "value_type": "4",
      "state": "0",
      "error": "",
      "lastclock": "1793233057",
      "lastvalue": "{\"window_seconds\":300,\"calls\":27,\"faults\":11,\"server_faults\":0,\"avg_ms\":1.2,\"max_ms\":12,\"clients_total\":201,\"pending_reconciliation\":1,\"etl_last_status\":\"success_with_rejects\",\"etl_last_age_seconds\":347,\"etl_last_rejected\":7}"
    },
    "soap.wsdl.operations": {
      "itemid": "50798",
      "key_": "soap.wsdl.operations",
      "value_type": "3",
      "state": "0",
      "error": "",
      "lastclock": "1793233058",
      "lastvalue": "3"
    }
  }
}
```
