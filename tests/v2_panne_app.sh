#!/usr/bin/env bash
# V2 — Panne d'un serveur applicatif pendant une charge.
# Exigence : le service reste disponible ; plus aucune erreur au-delà de
# 5 secondes. Mesure : requêtes perdues + durée de la période dégradée.
. "$(dirname "$0")/_lib.sh"

note "V2 — arrêt de app1 pendant des consultations continues (/resultat) via le répartiteur"

if ! vagrant status app1 | grep -q 'running'; then
  echo "ERREUR : app1 n'est pas démarrée."; exit 1
fi

SONDE_DUREE=25
(
  for i in $(seq 1 $((SONDE_DUREE * 4))); do
    printf '%s %s\n' "$(date +%s)" "$(http_code "http://${VIP}/resultat?matricule=100001")"
    sleep 0.25
  done
) > /tmp/v2.csv &
SONDE=$!

sleep 3
echo "-> vagrant halt app1"
T_HALT=$(date +%s)
vagrant halt app1
sleep 10
echo "-> vagrant up app1 (remise en service)"
vagrant up app1
wait $SONDE

total=$(wc -l < /tmp/v2.csv)
erreurs=$(awk '$2 != 200 { n++ } END { print n+0 }' /tmp/v2.csv)
premiere_err=$(awk '$2 != 200 { print $1; exit }' /tmp/v2.csv)
derniere_err=$(awk '$2 != 200 { t=$1 } END { print t+0 }' /tmp/v2.csv)
duree_degradee=$((derniere_err - premiere_err))

echo
echo "Réponses totales     : ${total}"
echo "Réponses en erreur   : ${erreurs} (≠200)"
echo "Première erreur      : $((premiere_err - T_HALT)) s après l'arrêt"
echo "Période dégradée     : ${duree_degradee} s"

if [ "$erreurs" -eq 0 ]; then
  echo "RÉSULTAT V2 : OK (éjection sans perte visible)"
elif [ "$duree_degradee" -le 5 ] && [ "$erreurs" -lt $((total / 20)) ]; then
  echo "RÉSULTAT V2 : ACCEPTABLE (dégradation < 5 s, pertes marginales)"
else
  echo "RÉSULTAT V2 : ÉCHEC"; exit 1
fi
