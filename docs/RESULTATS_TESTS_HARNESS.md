# Résultats des tests SOAP

Cible : `http://127.0.0.1:8099` — mode indisponibilité base : `harness`

Exécution UTC : 2026-10-29T00:01:56.949616+00:00

| # | Test | Résultat attendu | Statut |
|---|---|---|---|
| 1 | T01 WSDL publié avec les 3 opérations | HTTP 200 + 3 opérations | ✅ PASS |
| 2 | T02 getClientDetails : client existant | HTTP 200, client CLI-000010 | ✅ PASS |
| 3 | T03 getClientDetails : client inexistant | (500, 'Client', 'CLIENT_NOT_FOUND') | ✅ PASS |
| 4 | T04 getClientDetails : code invalide | (500, 'VALIDATION_ERROR', 'codeClient') | ✅ PASS |
| 5 | T05 searchClients : par nom (insensible à la casse) | tous les résultats ont nom=KONE | ✅ PASS |
| 6 | T06 searchClients : filtre statut + pagination | (200, '2', '3', 3, True) | ✅ PASS |
| 7 | T07 searchClients : taillePage hors limites | (500, 'VALIDATION_ERROR', 'taillePage') | ✅ PASS |
| 8 | T08 searchClients : statut hors énumération | (500, 'VALIDATION_ERROR', 'statut') | ✅ PASS |
| 9 | T09 searchClients : aucun résultat (pas une erreur) | (200, '0', 0) | ✅ PASS |
| 10 | T10 updateClient : modification valide (version+1, pending_mysql) | HTTP 200, version incrémentée | ✅ PASS |
| 11 | T11 cohérence : relecture après mise à jour | ('Test232116', 'suspendu') | ✅ PASS |
| 12 | T12 updateClient : conflit de version (verrou optimiste) | (500, 'VERSION_CONFLICT', 'versionAttendue') | ✅ PASS |
| 13 | T13 updateClient : e-mail invalide | (500, 'VALIDATION_ERROR', 'email') | ✅ PASS |
| 14 | T14 updateClient : e-mail déjà utilisé | (500, 'EMAIL_ALREADY_USED', 'email') | ✅ PASS |
| 15 | T15 updateClient : aucun champ à modifier | (500, 'VALIDATION_ERROR') | ✅ PASS |
| 16 | T16 updateClient : client inexistant | (500, 'CLIENT_NOT_FOUND') | ✅ PASS |
| 17 | T17 updateClient : téléphone invalide | (500, 'VALIDATION_ERROR', 'telephone') | ✅ PASS |
| 18 | T18 enveloppe SOAP invalide -> Fault | Fault HTTP 500 | ✅ PASS |
| 19 | T21 enveloppe vide -> Fault HTTP 500 | Fault HTTP 500 | ✅ PASS |
| 20 | T22 page zéro refusée | (500, 'VALIDATION_ERROR', 'page') | ✅ PASS |
| 21 | T23 caractères XML dans un filtre | HTTP 200, aucun résultat | ✅ PASS |
| 22 | T19 MongoDB indisponible -> Fault serveur | (500, 'Server', 'SERVICE_UNAVAILABLE') | ✅ PASS |
| 23 | T20 reprise après retour de MongoDB | HTTP 200 | ✅ PASS |

**Bilan : 23/23 tests réussis.**
