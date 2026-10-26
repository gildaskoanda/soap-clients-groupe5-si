#!/usr/bin/env bash
# V1 — Répartition : 20 appels successifs à /info via le répartiteur.
# Exigence : les N serveurs apparaissent tour à tour ; écart entre le plus
# et le moins sollicité < 20 %.
. "$(dirname "$0")/_lib.sh"

note "V1 — répartition sur ${NB_APP} serveurs applicatifs (VIP ${VIP})"

for _ in $(seq 1 20); do
  curl -s --max-time 3 "http://${VIP}/info" | sed -n 's/.*"hote": *"\([^"]*\)".*/\1/p'
done > /tmp/v1_hotes.txt

if [ ! -s /tmp/v1_hotes.txt ]; then
  echo "RÉSULTAT V1 : ÉCHEC (aucune réponse de /info via ${VIP})"
  exit 1
fi

echo "--- Distribution des 20 réponses ---"
sort /tmp/v1_hotes.txt | uniq -c | sort -rn

distincts=$(sort -u /tmp/v1_hotes.txt | wc -l | tr -d ' ')
max=$(sort /tmp/v1_hotes.txt | uniq -c | awk '{print $1}' | sort -n | tail -1)
min=$(sort /tmp/v1_hotes.txt | uniq -c | awk '{print $1}' | sort -n | head -1)
ecart=$(( (max - min) * 100 / max ))

echo
echo "Serveurs vus : ${distincts} / ${NB_APP} — écart max : ${ecart} % (exigence < 20 %)"
if [ "$distincts" -eq "$NB_APP" ] && [ "$ecart" -lt 20 ]; then
  echo "RÉSULTAT V1 : OK"
else
  echo "RÉSULTAT V1 : ÉCHEC"
  exit 1
fi
