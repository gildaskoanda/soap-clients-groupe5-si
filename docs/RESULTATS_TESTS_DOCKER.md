# Résultats des tests SOAP

Cible : `http://host.docker.internal:8080` — mode indisponibilité base : `skip`

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
| 11 | T11 cohérence : relecture après mise à jour | ('Test938960', 'suspendu') | ✅ PASS |
| 12 | T12 updateClient : conflit de version (verrou optimiste) | (500, 'VERSION_CONFLICT', 'versionAttendue') | ✅ PASS |
| 13 | T13 updateClient : e-mail invalide | (500, 'VALIDATION_ERROR', 'email') | ✅ PASS |
| 14 | T14 updateClient : e-mail déjà utilisé | (500, 'EMAIL_ALREADY_USED', 'email') | ✅ PASS |
| 15 | T15 updateClient : aucun champ à modifier | (500, 'VALIDATION_ERROR') | ✅ PASS |
| 16 | T16 updateClient : client inexistant | (500, 'CLIENT_NOT_FOUND') | ✅ PASS |
| 17 | T17 updateClient : téléphone invalide | (500, 'VALIDATION_ERROR', 'telephone') | ✅ PASS |
| 18 | T18 enveloppe SOAP invalide -> Fault | Fault HTTP 400/500 | ✅ PASS |

**Bilan : 18/18 tests réussis.**
