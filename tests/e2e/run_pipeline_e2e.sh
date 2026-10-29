#!/usr/bin/env bash
# =============================================================================
# Test de bout en bout de la chaîne principale (Exercice 7)
#   MySQL -> DAG 1 -> MongoDB -> SOAP updateClient -> DAG 2 -> MySQL
#
# Prérequis : pile démarrée
#   docker compose up -d mysql mongo airflow-db airflow-init airflow-webserver airflow-scheduler laravel
# Lancement (depuis n'importe où dans le dépôt, Git Bash / Linux / macOS) :
#   bash tests/e2e/run_pipeline_e2e.sh
#
# Le script est rejouable : il lit la version courante du client avant de le
# modifier et utilise une valeur de ville différente à chaque exécution.
# Il met le DAG 2 en pause pendant le test (pour éviter un déclenchement
# automatique au milieu du scénario) et restaure son état initial à la fin.
# =============================================================================
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1

BASE="${BASE_URL:-http://localhost:8080}"
CODE="${E2E_CLIENT:-CLI-000020}"
if [[ ! "$CODE" =~ ^CLI-[0-9]{6}$ ]]; then
  echo "E2E_CLIENT doit respecter le format CLI-000020."; exit 1
fi
NS="urn:ibam:clients:v1"
DAG1="clients_mysql_to_mongo"
DAG2="clients_reconcile_mongo_to_mysql"
TAG="e2e$(date +%s)"
NEW_CITY="Ville-${TAG}"

PASS=0
FAIL=0
ok()    { echo "PASS  $1"; PASS=$((PASS + 1)); }
ko()    { echo "FAIL  $1  -> $2"; FAIL=$((FAIL + 1)); }
check() { # check "libellé" "attendu" "obtenu"
  if [ "$2" = "$3" ]; then ok "$1"; else ko "$1" "attendu='$2' obtenu='$3'"; fi
}
contains() { # contains "libellé" "texte attendu" "contenu"
  case "$3" in *"$2"*) ok "$1" ;; *) ko "$1" "'$2' absent de : $(echo "$3" | head -c 300)" ;; esac
}

AF()    { docker compose exec -T airflow-scheduler airflow "$@" 2>/dev/null; }
MONGO() { docker compose exec -T mongo sh -c \
  'exec mongosh -u "$MONGO_INITDB_ROOT_USERNAME" -p "$MONGO_INITDB_ROOT_PASSWORD" --authenticationDatabase admin clients_db --quiet --eval "$1"' sh "$1" | tr -d '\r'; }
MYSQL() { docker compose exec -T mysql sh -c \
  'MYSQL_PWD="$MYSQL_PASSWORD" exec mysql -u"$MYSQL_USER" "$MYSQL_DATABASE" -N -B -e "$1"' sh "$1" | tr -d '\r'; }
soap()  { # soap Operation 'corps XML'
  curl --silent --show-error --max-time 20 -X POST "$BASE/soap/clients" \
    -H "Content-Type: text/xml; charset=utf-8" -H "SOAPAction: $NS#$1" \
    -d "<soapenv:Envelope xmlns:soapenv=\"http://schemas.xmlsoap.org/soap/envelope/\" xmlns:c=\"$NS\"><soapenv:Body>$2</soapenv:Body></soapenv:Envelope>"
}
xml_value() { # espace de noms métier, indépendamment du préfixe choisi par PHP
  python3 -c 'import sys,xml.etree.ElementTree as ET; root=ET.parse(sys.stdin); print(root.findtext(".//{urn:ibam:clients:v1}"+sys.argv[1], default=""))' "$1"
}

# run_dag <dag_id> <suffixe> <nb_taches_attendues> -> écrit success | failed | timeout
run_dag() {
  local dag="$1" rid="e2e_${TAG}_$2" expected="$3" out n_ok n_ko
  if ! AF dags trigger "$dag" -r "$rid" > /dev/null; then echo "trigger_impossible"; return; fi
  for _ in $(seq 1 60); do
    sleep 3
    out=$(AF tasks states-for-dag-run "$dag" "$rid")
    n_ko=$(echo "$out" | grep -ciE "failed|upstream_failed")
    n_ok=$(echo "$out" | grep -c "success")
    if [ "$n_ko" -gt 0 ]; then echo "failed"; return; fi
    if [ "$n_ok" -ge "$expected" ]; then echo "success"; return; fi
  done
  echo "timeout"
}

original_pause=""
restore() {
  if [ "$original_pause" = "true" ]; then AF dags pause "$DAG2" > /dev/null;
  elif [ "$original_pause" = "false" ]; then AF dags unpause "$DAG2" > /dev/null; fi
}
trap restore EXIT

echo "== Test de bout en bout : client $CODE, nouvelle ville '$NEW_CITY'"
echo

# ---- 0. Prérequis ------------------------------------------------------------
health=$(curl --silent --show-error --max-time 15 "$BASE/health")
contains "E0 service SOAP et MongoDB disponibles (/health)" '"mongodb":"up"' "$health"
if [ "$FAIL" -gt 0 ]; then echo "Pile non démarrée : arrêt."; exit 1; fi

# Airflow doit être démarré et avoir enregistré les deux DAG (compter 2 à 3 minutes après `docker compose up -d`).
if ! docker compose ps --status running --services 2>/dev/null | grep -qx "airflow-scheduler"; then
  ko "E0 airflow-scheduler démarré" "service arrêté : lancer 'docker compose up -d' puis attendre 2 à 3 minutes"
  echo "Pile incomplète : arrêt."; exit 1
fi
ok "E0 airflow-scheduler démarré"
dags_ready=0
for _ in $(seq 1 60); do
  listing=$(AF dags list)
  if echo "$listing" | grep -q "$DAG1" && echo "$listing" | grep -q "$DAG2"; then dags_ready=1; break; fi
  sleep 5
done
if [ "$dags_ready" -eq 1 ]; then ok "E0 DAG enregistrés dans Airflow"; else
  ko "E0 DAG enregistrés dans Airflow" "absents après 5 min : voir 'airflow dags list-import-errors'"
  echo "Airflow n'est pas prêt : arrêt."; exit 1
fi
original_pause=$(AF dags list --output json | python3 -c 'import json,sys; d=next(x for x in json.load(sys.stdin) if x["dag_id"]==sys.argv[1]); print(str(d["is_paused"]).lower())' "$DAG2")
if [ "$original_pause" != "true" ] && [ "$original_pause" != "false" ]; then
  echo "Impossible de déterminer l’état initial du DAG de réconciliation."; exit 1
fi
AF dags pause "$DAG2" > /dev/null

# ---- 1. DAG 1 : MySQL -> MongoDB ---------------------------------------------
check "E1 MySQL contient 208 lignes fictives" "208" "$(MYSQL 'SELECT COUNT(*) FROM clients')"
check "E1 DAG 1 exécuté avec succès (3 tâches)" "success" "$(run_dag "$DAG1" 1 3)"
check "E1 MongoDB contient 201 clients valides" "201" "$(MONGO 'print(db.clients.countDocuments({}))')"
check "E1 MongoDB conserve 7 rejets de qualité" "7" "$(MONGO 'print(db.clients_rejected.countDocuments({}))')"

# ---- 2. Idempotence ----------------------------------------------------------
check "E2 relance du DAG 1 : succès" "success" "$(run_dag "$DAG1" 2 3)"
check "E2 relance : 0 insertion (idempotence)" "0" \
  "$(MONGO 'print(db.etl_runs.find().sort({_id:-1}).limit(1).toArray()[0].inserted)')"
check "E2 relance : toujours 201 clients (pas de doublon)" "201" "$(MONGO 'print(db.clients.countDocuments({}))')"

# ---- 3. SOAP : lecture puis modification -------------------------------------
resp=$(soap getClientDetails "<c:getClientDetailsRequest><c:codeClient>$CODE</c:codeClient></c:getClientDetailsRequest>")
check "E3 getClientDetails renvoie le client" "$CODE" "$(xml_value codeClient <<< "$resp")"
old_version=$(xml_value version <<< "$resp")
if [[ ! "$old_version" =~ ^[1-9][0-9]*$ ]]; then
  ko "E3 version exploitable" "version absente ou invalide : arrêt du scénario"; exit 1
fi
old_city=$(MYSQL "SELECT ville FROM clients WHERE code_client='$CODE'")

resp=$(soap updateClient "<c:updateClientRequest><c:codeClient>$CODE</c:codeClient><c:versionAttendue>$old_version</c:versionAttendue><c:ville>$NEW_CITY</c:ville></c:updateClientRequest>")
check "E4 updateClient : nouvelle ville renvoyée" "$NEW_CITY" "$(xml_value ville <<< "$resp")"
check "E4 updateClient : synchronisation = pending_mysql" "pending_mysql" "$(xml_value synchronisation <<< "$resp")"
new_version=$(xml_value version <<< "$resp")
check "E4 updateClient : version incrémentée" "$((old_version + 1))" "$new_version"

# ---- 4. État intermédiaire : MongoDB modifié, MySQL inchangé ----------------
check "E5 MongoDB : sync_status = pending_mysql" "pending_mysql" \
  "$(MONGO "print(db.clients.findOne({code_client:'$CODE'}).sync_status)")"
check "E5 MySQL inchangé (référence = MongoDB, pas de retour automatique)" "$old_city" \
  "$(MYSQL "SELECT ville FROM clients WHERE code_client='$CODE'")"

# ---- 5. Le DAG 1 ne réécrase pas la modification SOAP -----------------------
check "E6 DAG 1 relancé : succès" "success" "$(run_dag "$DAG1" 3 3)"
check "E6 modification SOAP conservée dans MongoDB" "$NEW_CITY" \
  "$(MONGO "print(db.clients.findOne({code_client:'$CODE'}).ville)")"
conflicts=$(MONGO 'print(db.etl_runs.find().sort({_id:-1}).limit(1).toArray()[0].conflicts_skipped)')
if [ "${conflicts:-0}" -ge 1 ]; then ok "E6 conflit détecté et ignoré par le DAG 1 ($conflicts)"; else ko "E6 conflit détecté" "conflicts_skipped=$conflicts"; fi

# ---- 6. DAG 2 : MongoDB -> MySQL ---------------------------------------------
AF dags unpause "$DAG2" > /dev/null
check "E7 DAG 2 (réconciliation) exécuté avec succès" "success" "$(run_dag "$DAG2" 1 1)"
check "E7 MySQL a reçu la modification" "$NEW_CITY" "$(MYSQL "SELECT ville FROM clients WHERE code_client='$CODE'")"
check "E7 MongoDB : sync_status = synced" "synced" \
  "$(MONGO "print(db.clients.findOne({code_client:'$CODE'}).sync_status)")"
applied=$(MONGO "print(db.reconciliation_log.countDocuments({code_client:'$CODE', action:'applied'}))")
if [ "${applied:-0}" -ge 1 ]; then ok "E7 journal de réconciliation : action 'applied' ($applied)"; else ko "E7 journal" "applied=$applied"; fi

# ---- 7. Lecture finale -------------------------------------------------------
resp=$(soap getClientDetails "<c:getClientDetailsRequest><c:codeClient>$CODE</c:codeClient></c:getClientDetailsRequest>")
check "E8 getClientDetails : synchronisation = synced" "synced" "$(xml_value synchronisation <<< "$resp")"

# ---- 8. La protection SOAP persiste après réconciliation ---------------------
check "E9 import après réconciliation : succès" "success" "$(run_dag "$DAG1" 4 3)"
check "E9 valeur SOAP conservée" "$NEW_CITY" \
  "$(MONGO "print(db.clients.findOne({code_client:'$CODE'}).ville)")"
check "E9 version métier inchangée" "$new_version" \
  "$(MONGO "print(db.clients.findOne({code_client:'$CODE'}).version)")"

echo
echo "== Bilan : $PASS réussis, $FAIL échecs"
[ "$FAIL" -eq 0 ]
