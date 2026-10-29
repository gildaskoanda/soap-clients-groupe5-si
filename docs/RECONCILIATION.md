# Stratégie de réconciliation MongoDB → MySQL

## Principe
- **MongoDB est la base de référence** : en cas de divergence, la valeur MongoDB l'emporte.
- Les clients naissent dans MySQL (DAG 1 → MongoDB). Les modifications faites par le service SOAP restent dans MongoDB puis sont **renvoyées** vers MySQL par le DAG 2. Le service SOAP n'écrit jamais dans MySQL (pas de double écriture, donc pas de transaction distribuée).

## Cycle de vie d'une modification

| Étape | Qui | Effet sur le document MongoDB |
|---|---|---|
| 1. `updateClient` | Service SOAP | champs modifiés, `version += 1`, `locally_modified = true`, `sync_status = pending_mysql` |
| 2. DAG 1 (horaire) | Airflow | **ne touche pas** ce client (compté dans `conflicts_skipped`) : la modification SOAP n'est jamais écrasée par la source |
| 3. DAG 2 (`30 * * * *`) | Airflow | lit les documents `locally_modified = true`, applique `UPDATE` sur MySQL (nom, prénom, e-mail, téléphone, ville, statut) |
| 4. Acquittement | Airflow | `locally_modified = false`, `sync_status = synced`, `mysql_updated_at` = nouvel `updated_at` MySQL — **uniquement si `version` n'a pas changé** depuis la lecture |

Si une nouvelle modification SOAP arrive pendant l'étape 3, l'acquittement échoue volontairement (filtre sur `version`) : le client reste en attente et sera réappliqué au passage suivant. Rien n'est perdu.

## Détection et résolution des conflits
Un **conflit** = la ligne MySQL a changé depuis la dernière synchronisation (`updated_at` MySQL ≠ `mysql_updated_at` mémorisé dans MongoDB).

| Situation | Décision | Traçabilité |
|---|---|---|
| Ligne MySQL inchangée | Application normale | `reconciliation_log.action = applied` |
| Ligne MySQL modifiée entre-temps | **MongoDB gagne** (référence) | `applied_conflict_mongo_wins` + copie de l'ancienne ligne MySQL dans `mysql_overwritten` |
| Ligne absente de MySQL | Aucune insertion automatique | `sync_status = conflict`, `skipped_missing_in_mysql` |
| Erreur MySQL (ex. e-mail déjà utilisé) | Le client passe en `conflict`, les suivants continuent | `failed` + message ; le DAG se termine en erreur pour alerter |

## Garanties
- **Idempotence** : relancer le DAG 2 ne réapplique rien (plus aucun document `locally_modified`).
- **Isolation des pannes** : un client en échec ne bloque pas les autres.
- **Pas de ping-pong** : après réconciliation, `mysql_updated_at` est resynchronisé ; le DAG 1 suivant ne voit aucune différence et n'incrémente pas la version.
- **Audit** : `reconciliation_log` conserve chaque décision avec `run_id`, version et horodatage.

## Limites connues (à citer en soutenance)
- Fenêtre d'incohérence : jusqu'à ~1 h entre une modification SOAP et sa visibilité dans MySQL (planification du DAG 2, déclenchable à la demande).
- Les créations/suppressions de clients ne sont pas gérées dans ce sens (le périmètre du service SOAP est lecture + mise à jour).
- Les écritures Mongo ne passent pas par une transaction multi-documents (MongoDB autonome) : l'atomicité repose sur un seul document et le verrou optimiste.
- Stratégie alternative envisageable : journal d'événements (*outbox*) ou Change Streams (nécessite un replica set MongoDB).
