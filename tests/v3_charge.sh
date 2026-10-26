#!/usr/bin/env bash
# V3 — Montée en charge : ab -n 2000 -c 50 avec N serveurs, puis N=4.
# Exigence : le débit augmente quand on ajoute des serveurs. Honnêteté :
# toutes les VM partagent le processeur de l'hôte — le gain n'est pas
# proportionnel et peut même être nul ; c'est un résultat à commenter.
. "$(dirname "$0")/_lib.sh"

# ab sur l'hôte s'il est installé, sinon sur la machine obs (EXTENSIONS=1).
lancer_ab() {
  local url="http://${VIP}/resultat?matricule=100001"
  if command -v ab >/dev/null 2>&1; then
    ab -n 2000 -c 50 -q "$url" 2>/dev/null
  elif vagrant status obs 2>/dev/null | grep -q 'running'; then
    vagrant ssh obs -c "ab -n 2000 -c 50 -q '$url' 2>/dev/null" | tr -d '\r'
  else
    echo "ERREUR : ni 'ab' sur l'hôte, ni la machine obs démarrée (EXTENSIONS=1)." >&2
    return 1
  fi
}

mesure() {
  lancer_ab | tee /tmp/v3_ab.txt | grep -E 'Requests per second|Failed requests|Time taken'
  grep 'Requests per second' /tmp/v3_ab.txt | awk '{print $4}'
}

note "V3 — test de charge sur ${NB_APP} serveurs (ab -n 2000 -c 50)"
echo "--- N = ${NB_APP} ---"
R2=$(mesure | tail -1)
echo "Débit mesuré (N=${NB_APP}) : ${R2} req/s"

if [ "$NB_APP" -lt 4 ]; then
  echo
  echo "-> passage à N=4 : NB_APP=4 vagrant up app3 app4"
  NB_APP=4 vagrant up app3 app4
  # Attente de la mise à jour automatique du répartiteur (déclencheur) et
  # de la visibilité des 4 serveurs.
  for _ in $(seq 1 30); do
    vus=$(for _ in $(seq 1 12); do curl -s --max-time 2 "http://${VIP}/info"; done \
          | grep -o '"hote": *"[^"]*"' | sort -u | wc -l | tr -d ' ')
    [ "$vus" -ge 4 ] && break
    sleep 2
  done
  echo "Serveurs visibles via /info : ${vus}"
fi

echo "--- N = 4 ---"
R4=$(mesure | tail -1)
echo "Débit mesuré (N=4) : ${R4} req/s"

echo
echo "Comparaison : ${R2} -> ${R4} req/s pour N=${NB_APP} -> 4."
echo "Résultat honnête à commenter dans le dossier (CPU partagé, bascule psycopg2, etc.)."
