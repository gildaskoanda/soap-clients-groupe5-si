# Documentation du service SOAP de clients

| | |
|---|---|
| **WSDL** | `http://localhost:8080/soap/clients?wsdl` (fichier source : `laravel-overlay/resources/wsdl/clients.wsdl`) |
| **Endpoint** | `POST http://localhost:8080/soap/clients` — `Content-Type: text/xml` |
| **Protocole** | SOAP 1.1, style `document`, usage `literal` |
| **Espace de noms** | `urn:ibam:clients:v1` |
| **Base de référence** | MongoDB (`clients_db.clients`) — le service ne touche jamais MySQL |
| **Authentification** | Aucune (hors périmètre du sujet) ; à placer derrière une passerelle en production |

## 1. Type `Client`

| Champ | Type | Obligatoire | Description |
|---|---|---|---|
| `codeClient` | string | oui | Identifiant métier `CLI-000000` |
| `nom` | string | oui | Nom, stocké en MAJUSCULES |
| `prenom` | string | oui | Prénom, stocké en Casse Titre |
| `email` | string | oui | Unique, stocké en minuscules |
| `telephone` | string | non | Ex. `+226 70 11 22 33` |
| `ville` | string | non | |
| `pays` | string | non | Défaut `Burkina Faso` |
| `statut` | `actif` \| `inactif` \| `suspendu` | oui | |
| `dateInscription` | string (ISO `AAAA-MM-JJ`) | non | |
| `version` | int | oui | Compteur de version (verrou optimiste), commence à 1 |
| `synchronisation` | string | non | `synced`, `pending_mysql` (modifié via SOAP, pas encore dans MySQL) ou `conflict` |

## 2. Opérations

### 2.1 `getClientDetails`
Retourne un client par son code.

| Paramètre | Type | Oblig. | Règle |
|---|---|---|---|
| `codeClient` | string | oui | `^CLI-\d{6}$` |

Réponse `getClientDetailsResponse` : `client` (type `Client`).
Faults : `VALIDATION_ERROR`, `CLIENT_NOT_FOUND`, `SERVICE_UNAVAILABLE`.

### 2.2 `searchClients`
Recherche paginée, triée par nom, prénom puis code. Sans critère : tous les clients, paginés.

| Paramètre | Type | Oblig. | Règle |
|---|---|---|---|
| `nom` | string | non | 2 à 80 car. ; contient, insensible à la casse |
| `ville` | string | non | 2 à 80 car. ; contient, insensible à la casse |
| `statut` | enum | non | `actif`, `inactif`, `suspendu` |
| `page` | int | non | ≥ 1 (défaut 1) |
| `taillePage` | int | non | 1 à 100 (défaut 20) |

Réponse `searchClientsResponse` : `total` (int, nombre total de correspondances), `page`, `taillePage`, `clients` (0..n `Client`).
Un résultat vide est une réponse normale (`total = 0`), pas une erreur.
Faults : `VALIDATION_ERROR`, `SERVICE_UNAVAILABLE`.

### 2.3 `updateClient`
Modifie les champs fournis (les champs omis restent inchangés). L'écriture est faite **dans MongoDB** ; MySQL est mis à jour plus tard par le DAG de réconciliation.

| Paramètre | Type | Oblig. | Règle |
|---|---|---|---|
| `codeClient` | string | oui | `^CLI-\d{6}$` |
| `versionAttendue` | int | non | ≥ 1 ; si fournie, doit égaler la version courante (verrou optimiste) |
| `nom`, `prenom` | string | non | 2 à 80 car. : lettres, espaces, apostrophes, tirets ; pas de chiffres |
| `email` | string | non | adresse valide, ≤ 190 car., **unique** |
| `telephone` | string | non | `^\+?[0-9][0-9 ]{7,17}$` |
| `ville` | string | non | 2 à 80 car. |
| `statut` | enum | non | `actif`, `inactif`, `suspendu` |

Au moins un champ modifiable est obligatoire.
Réponse `updateClientResponse` : `message` (string), `client` (état après modification, `version` incrémentée, `synchronisation = pending_mysql`).
Faults : `VALIDATION_ERROR`, `CLIENT_NOT_FOUND`, `VERSION_CONFLICT`, `EMAIL_ALREADY_USED`, `SERVICE_UNAVAILABLE`.

La mise à jour est **atomique** (`findOneAndUpdate` filtré sur `code_client` et `version`) : deux modifications simultanées ne peuvent pas s'écraser, la seconde reçoit `VERSION_CONFLICT`.

## 3. Erreurs SOAP (Fault)

Les erreurs sont des `SOAP-ENV:Fault` renvoyés avec le statut HTTP **500** (exigence SOAP 1.1). Le champ `detail` contient l'élément `ClientFault` déclaré dans le WSDL :

```xml
<SOAP-ENV:Fault>
  <faultcode>SOAP-ENV:Client</faultcode>
  <faultstring>Aucun client avec le code CLI-999999.</faultstring>
  <detail>
    <ns1:ClientFault xmlns:ns1="urn:ibam:clients:v1">
      <ns1:code>CLIENT_NOT_FOUND</ns1:code>
      <ns1:message>Aucun client avec le code CLI-999999.</ns1:message>
      <ns1:champ>codeClient</ns1:champ>
    </ns1:ClientFault>
  </detail>
</SOAP-ENV:Fault>
```

| `faultcode` | `code` (détail) | `champ` | Quand | Que faire côté client |
|---|---|---|---|---|
| Client | `VALIDATION_ERROR` | champ fautif | Paramètre absent, mal formé ou hors limites | Corriger la requête |
| Client | `CLIENT_NOT_FOUND` | `codeClient` | Aucun client avec ce code | Vérifier le code |
| Client | `EMAIL_ALREADY_USED` | `email` | E-mail porté par un autre client | Choisir un autre e-mail |
| Client | `VERSION_CONFLICT` | `versionAttendue` | Version obsolète ou modification concurrente | Relire (`getClientDetails`) puis réessayer |
| Server | `SERVICE_UNAVAILABLE` | — | MongoDB injoignable (délai 2 s) | Réessayer plus tard |
| Server | `INTERNAL_ERROR` | — | Erreur inattendue (détail dans les logs, jamais exposé) | Contacter l'exploitation |

Enveloppe vide ou non SOAP : Fault `Client`/`Server` sans détail `ClientFault`.

## 4. Exemples

**Requête** `updateClient` :
```xml
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:c="urn:ibam:clients:v1">
  <soapenv:Body>
    <c:updateClientRequest>
      <c:codeClient>CLI-000010</c:codeClient>
      <c:versionAttendue>1</c:versionAttendue>
      <c:ville>Ouagadougou</c:ville>
    </c:updateClientRequest>
  </soapenv:Body>
</soapenv:Envelope>
```
**Réponse** :
```xml
<ns1:updateClientResponse>
  <ns1:message>Client mis à jour dans MongoDB (en attente de réconciliation vers MySQL).</ns1:message>
  <ns1:client>
    <ns1:codeClient>CLI-000010</ns1:codeClient> ... <ns1:version>2</ns1:version>
    <ns1:synchronisation>pending_mysql</ns1:synchronisation>
  </ns1:client>
</ns1:updateClientResponse>
```
Autres requêtes prêtes à l'emploi : `tests/soapui/requests/`.

## 5. Supervision des appels
Chaque appel est journalisé dans `soap_calls` (opération, succès, code de Fault, durée) avec purge automatique à 7 jours ; Zabbix lit l'agrégat via `GET /monitoring/stats`.
