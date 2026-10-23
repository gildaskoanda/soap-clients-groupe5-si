// Initialisation MongoDB (exécuté une seule fois, au premier démarrage du conteneur).
// MongoDB est la BASE DE RÉFÉRENCE du service SOAP.
const dbName = 'clients_db';
const appDb = db.getSiblingDB(dbName);

appDb.createUser({
  user: 'app',
  pwd: process.env.MONGO_APP_PASSWORD || 'app_password',
  roles: [{ role: 'readWrite', db: dbName }],
});

// --- clients : collection de référence, validée par JSON Schema ---------------
appDb.createCollection('clients', {
  validator: {
    $jsonSchema: {
      bsonType: 'object',
      required: ['code_client', 'nom', 'prenom', 'email', 'statut', 'version'],
      properties: {
        code_client: { bsonType: 'string', pattern: '^CLI-[0-9]{6}$' },
        nom: { bsonType: 'string', minLength: 2, maxLength: 80 },
        prenom: { bsonType: 'string', minLength: 2, maxLength: 80 },
        email: { bsonType: 'string', maxLength: 190 },
        telephone: { bsonType: ['string', 'null'] },
        ville: { bsonType: ['string', 'null'] },
        pays: { bsonType: ['string', 'null'] },
        statut: { enum: ['actif', 'inactif', 'suspendu'] },
        date_inscription: { bsonType: ['string', 'null'] },
        version: { bsonType: ['int', 'long'], minimum: 1 },
        locally_modified: { bsonType: 'bool' },
        sync_status: { enum: ['synced', 'pending_mysql', 'conflict'] },
        source: { enum: ['mysql', 'soap'] },
      },
    },
  },
  validationLevel: 'strict',
  validationAction: 'error',
});
appDb.clients.createIndex({ code_client: 1 }, { unique: true, name: 'uq_code_client' });
appDb.clients.createIndex({ email: 1 }, { unique: true, name: 'uq_email' });
appDb.clients.createIndex({ nom: 1, prenom: 1 }, { name: 'idx_nom_prenom' });
appDb.clients.createIndex({ ville: 1 }, { name: 'idx_ville' });
appDb.clients.createIndex({ locally_modified: 1 }, { name: 'idx_locally_modified', partialFilterExpression: { locally_modified: true } });

// --- collections techniques ------------------------------------------------------
appDb.createCollection('clients_rejected');     // lignes refusées par le contrôle qualité (avec motifs)
appDb.createCollection('etl_runs');             // bilan de chaque exécution Airflow
appDb.createCollection('reconciliation_log');   // historique des réconciliations Mongo -> MySQL
appDb.createCollection('soap_calls');           // appels SOAP (supervision), purgés après 7 jours
appDb.soap_calls.createIndex({ ts: 1 }, { expireAfterSeconds: 7 * 24 * 3600, name: 'ttl_ts' });
appDb.clients_rejected.createIndex({ run_id: 1 });
appDb.etl_runs.createIndex({ finished_at: -1 });
