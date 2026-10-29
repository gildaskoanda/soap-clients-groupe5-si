# Contrat du service SOAP de clients

Projet IBAM 2026 — Groupe 5 SI — Exercice 7.

## 1. Accès et protocole

| Élément | Valeur locale |
|---|---|
| Endpoint | `POST http://localhost:8080/soap/clients` |
| Contrat WSDL | `GET http://localhost:8080/soap/clients?wsdl` |
| Version | SOAP 1.1, WSDL 1.1, document/literal |
| Espace de noms métier | `urn:ibam:clients:v1` |
| Enveloppe | `http://schemas.xmlsoap.org/soap/envelope/` |
| Type de contenu | `text/xml; charset=utf-8` |
| SOAPAction | `urn:ibam:clients:v1#` suivi du nom de l’opération |
| Base du service | MongoDB, collection `clients` dans `clients_db` |

Le fichier contractuel est [clients.wsdl](../laravel-app/resources/wsdl/clients.wsdl).
Laravel remplace son marqueur d’adresse au moment de la publication. Le service
ne lit ni ne modifie directement MySQL. L’identifiant échangé est `codeClient`
(exemple : `CLI-000010`), et non l’identifiant interne MySQL ou MongoDB.

## 2. Structure commune d’un client

| Champ XML | Type | Présence et signification |
|---|---|---|
| `codeClient` | chaîne | Obligatoire ; identifiant stable `CLI-` suivi de six chiffres |
| `nom`, `prenom` | chaînes | Obligatoires ; 2 à 80 caractères |
| `email` | chaîne | Obligatoire ; adresse normalisée en minuscules |
| `telephone`, `ville`, `pays` | chaînes | Facultatifs ; absents du XML si non renseignés |
| `statut` | énumération | `actif`, `inactif` ou `suspendu` |
| `dateInscription` | chaîne | Facultative ; date métier au format `AAAA-MM-JJ` |
| `version` | entier | Obligatoire ; commence à 1, augmente à chaque modification métier |
| `synchronisation` | chaîne | `synced`, `pending_mysql` ou `conflict` |

L’ordre des éléments suit les séquences du WSDL. Une recherche retourne zéro,
un ou plusieurs éléments `clients` ; une consultation retourne un élément `client`.

## 3. Opérations et paramètres

### getClientDetails

Entrée : `getClientDetailsRequest`, avec `codeClient` obligatoire.

Sortie : `getClientDetailsResponse`, contenant `client`.
Une fiche inexistante produit `CLIENT_NOT_FOUND`.

### searchClients

Entrée : `searchClientsRequest`. Tous les paramètres sont facultatifs.

| Paramètre | Règle | Valeur par défaut |
|---|---|---|
| `nom` | 2 à 80 caractères ; recherche partielle, sans distinction majuscules/minuscules | Aucun filtre |
| `ville` | 2 à 80 caractères ; recherche partielle, sans distinction majuscules/minuscules | Aucun filtre |
| `statut` | Une des trois valeurs autorisées | Aucun filtre |
| `page` | Entier supérieur ou égal à 1 | 1 |
| `taillePage` | Entier entre 1 et 100 inclus | 20 |

Les filtres se combinent avec ET. Les caractères spéciaux sont traités comme du
texte, pas comme une expression régulière fournie par l’appelant.
Le tri se fait par nom, prénom puis code client. L’insensibilité à la casse ne
signifie pas que les accents sont ignorés.

Sortie : `searchClientsResponse` avec `total`, `page`, `taillePage` et les
éléments `clients`. Une recherche sans résultat est un succès : `total=0`.

### updateClient

Entrée : `updateClientRequest`, avec `codeClient` obligatoire, puis
`versionAttendue` facultative et au moins un champ modifiable.

| Champ | Validation et normalisation |
|---|---|
| `versionAttendue` | Entier >= 1 ; doit correspondre à la version lue |
| `nom`, `prenom` | 2 à 80 caractères ; lettres, espaces, apostrophes et tirets ; première position : lettre |
| `nom` | Mis en majuscules après validation |
| `prenom` | Mis en casse de titre après validation |
| `email` | Adresse valide, 190 caractères maximum, mise en minuscules, unique |
| `telephone` | 8 à 18 caractères composés de chiffres et d’espaces ; `+` initial facultatif, premier caractère après `+` numérique |
| `ville` | 2 à 80 caractères |
| `statut` | `actif`, `inactif` ou `suspendu` |

Les espaces en début et en fin sont retirés. Un champ absent conserve sa valeur.
Une chaîne vide est refusée pour les champs modifiables. `codeClient`, `pays` et
`dateInscription` ne sont pas modifiables par cette opération.

Sortie : `updateClientResponse` avec `message` et `client`. La version augmente
de 1 et la synchronisation devient `pending_mysql`. Une écriture concurrente
détectée produit un conflit ; relire la fiche avant de réessayer. Il est conseillé
de transmettre `versionAttendue` pour protéger le travail de l’utilisateur.

## 4. Exemple complet

Requête de consultation :

```xml
<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:c="urn:ibam:clients:v1">
  <soap:Body>
    <c:getClientDetailsRequest>
      <c:codeClient>CLI-000010</c:codeClient>
    </c:getClientDetailsRequest>
  </soap:Body>
</soap:Envelope>
```

La réponse comporte `getClientDetailsResponse/client` avec les champs du §2.
Des requêtes complètes pour les trois opérations sont disponibles dans
[tests/soapui/requests](../tests/soapui/requests).

```sh
curl --silent --show-error http://localhost:8080/soap/clients \
  -H 'Content-Type: text/xml; charset=utf-8' \
  -H 'SOAPAction: urn:ibam:clients:v1#getClientDetails' \
  --data-binary @tests/soapui/requests/01_getClientDetails_ok.xml
```

## 5. Erreurs SOAP

Une réponse métier normale utilise HTTP 200. Une Fault utilise HTTP 500.
`faultcode` indique la famille SOAP (`Client` ou `Server`) ; le code métier est
dans `detail/ClientFault/code`. Les préfixes XML peuvent varier : leur espace de
noms, et non leur orthographe, identifie les éléments.

| Code métier | Famille | Cause et réaction attendue |
|---|---|---|
| `VALIDATION_ERROR` | Client | Paramètre incorrect ; corriger le champ indiqué |
| `CLIENT_NOT_FOUND` | Client | Code valide mais client absent ; vérifier le code |
| `EMAIL_ALREADY_USED` | Client | E-mail déjà affecté à une autre fiche ; choisir une autre adresse |
| `VERSION_CONFLICT` | Client | Version devenue obsolète ; relire avant modification |
| `SERVICE_UNAVAILABLE` | Server | Accès à MongoDB impossible ; vérifier la base et réessayer |
| `INTERNAL_ERROR` | Server | Erreur technique inattendue ; consulter les journaux techniques |

Exemple de corps de Fault (à l’intérieur de `soap:Body`) :

```xml
<soap:Fault xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <faultcode>soap:Client</faultcode>
  <faultstring>Aucun client avec le code CLI-999999.</faultstring>
  <detail>
    <c:ClientFault xmlns:c="urn:ibam:clients:v1">
      <c:code>CLIENT_NOT_FOUND</c:code>
      <c:message>Aucun client avec le code CLI-999999.</c:message>
      <c:champ>codeClient</c:champ>
    </c:ClientFault>
  </detail>
</soap:Fault>
```

Une enveloppe vide ou mal formée peut produire une Fault de protocole sans détail
métier. Les erreurs du serveur ne doivent pas révéler les identifiants de connexion.

## 6. Périmètre de démonstration

L’installation livrée utilise des clients fictifs et un accès local. Aucune
authentification SOAP n’est implémentée : les trois opérations sont accessibles
à tout programme pouvant joindre l’endpoint. Un déploiement accessible à d’autres
utilisateurs demanderait HTTPS, authentification et autorisation des modifications.
Les comptes des bases et de Zabbix sont distincts de cette question.
