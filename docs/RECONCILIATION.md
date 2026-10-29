# Réconciliation entre MongoDB et MySQL

## 1. Rôle des bases

MySQL contient le jeu de départ. Le service SOAP consulte et modifie uniquement
MongoDB. Le code client est la clé commune ; les identifiants internes des bases
ne servent pas au rapprochement.

Le DAG `clients_mysql_to_mongo` importe les nouvelles fiches et actualise les
fiches encore gérées par la source MySQL. Dès qu’une fiche est modifiée par SOAP,
MongoDB en conserve la maîtrise, y compris après le retour vers MySQL. Le marqueur
`source=soap` reste conservé. Les nouvelles modifications de cette fiche doivent
passer par le service SOAP.

## 2. Champs de suivi

| Champ MongoDB | Utilité |
|---|---|
| `version` | Numéro de version métier, utilisé pour les écritures conditionnelles |
| `source` | `mysql` à l’import, `soap` dès une modification via le service |
| `locally_modified` | Vrai tant qu’une modification doit être renvoyée vers MySQL |
| `sync_status` | `synced`, `pending_mysql` ou `conflict` |
| `mysql_updated_at` | Date MySQL connue lors de la dernière synchronisation |
| `updated_at` | Date de modification du document MongoDB |

La date MySQL sert à repérer une divergence, mais ne suffit pas seule à garantir
la cohérence : plusieurs modifications peuvent partager la même seconde.

## 3. Retour MongoDB → MySQL

Le DAG `clients_reconcile_mongo_to_mysql`, programmé à la minute 30 de chaque
heure, traite les documents avec `locally_modified=true`.

1. Lire la version MongoDB et chercher la ligne MySQL par `code_client`.
2. Verrouiller la ligne MySQL pendant la lecture et la mise à jour.
3. Comparer `updated_at` MySQL avec la date connue dans MongoDB.
4. Écrire `nom`, `prenom`, `email`, `telephone`, `ville` et `statut` dans MySQL.
5. Enregistrer l’opération dans `reconciliation_log`.
6. Acquitter la synchronisation uniquement si la version MongoDB n’a pas changé.

En cas de divergence, **MongoDB l’emporte**. L’ancienne ligne MySQL est conservée
dans le journal du conflit. Une ligne MySQL manquante est signalée ; elle n’est
pas recréée automatiquement. Une erreur sur une fiche ne doit pas bloquer le
traitement des autres ; le DAG signale toutefois les échecs à la fin.

## 4. Protection contre les chevauchements

Un lot MySQL peut être extrait avant une modification SOAP puis chargé après sa
réconciliation. Pour éviter qu’il rétablisse les anciennes valeurs :

- une fiche `source=soap` ne reçoit plus d’actualisation métier depuis MySQL ;
- un lot dont la date source est plus ancienne que la date déjà connue est ignoré ;
- une mise à jour d’import vérifie atomiquement la version, la date de référence
  et l’absence de modification SOAP ;
- les compteurs indiquent les écritures réellement effectuées, pas seulement
  les écritures envisagées.

`max_active_runs=1` limite les exécutions d’un même DAG. Il ne constitue pas un
verrou commun aux deux DAG. La protection des données repose donc aussi sur les
conditions d’écriture, même lors d’un déclenchement manuel simultané.

## 5. Reprise après incident

| Incident | Comportement |
|---|---|
| MongoDB ou MySQL indisponible | Échec visible, puis nouvelle tentative Airflow |
| Ligne MySQL absente | État `conflict`, intervention nécessaire |
| Contrainte MySQL refusée, par exemple e-mail en double | Ligne maintenue en attente, erreur journalisée |
| Nouvelle modification SOAP pendant le retour MySQL | La nouvelle version reste en attente pour le passage suivant |
| Arrêt après l’écriture MySQL et avant l’acquittement MongoDB | La fiche reste en attente ; une nouvelle exécution réapplique les valeurs |

Les deux bases ne partagent pas de transaction. La cohérence est donc différée,
avec reprise idempotente : réappliquer les mêmes valeurs ne crée pas un deuxième
client. Le délai dépend des horaires des DAG, des tentatives et de la disponibilité
des bases ; il ne s’agit pas d’une réplication instantanée.

## 6. Vérification et limites

Le scénario [de démonstration](GUIDE_DEMONSTRATION.md) montre la modification SOAP,
son absence temporaire dans MySQL, puis son retour par Airflow. Les tests Python
couvrent aussi un lot ancien, une date identique et des écritures concurrentes.

La suppression des clients, la fusion de deux fiches et la résolution manuelle
automatisée des conflits ne font pas partie de cet exercice. Une modification
MySQL d’une fiche déjà gérée par SOAP n’est pas propagée vers MongoDB ; l’équipe
doit utiliser `updateClient` pour les évolutions de cette fiche.
