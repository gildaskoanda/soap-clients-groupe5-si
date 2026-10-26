#!/usr/bin/env bash
# V6 — Panne du répartiteur actif (extension E1) : vagrant halt lb1.
# Exigence : le service reste joignable à la même adresse (la VIP), en
# moins de 5 secondes. Mesure : temps de reprise après bascule VRRP.
. "$(dirname "$0")/_lib.sh"

note "V6 — arrêt de lb1 pendant une sonde continue sur la VIP ${VIP}"

if ! awk -F'\t' '$1 == "lb2"' config/noeuds.tsv | grep -q .; then
  echo "ERREUR : lb2 absent (EXTENSIONS=0). V6 demande l'extension E1 : EXTENSIONS=1 vagrant up lb2"; exit 1
fi
if ! vagrant status lb1 | grep -q 'running'; then
  echo "ERREUR : lb1 n'est pas démarré."; exit 1
fi

(
  for _ in $(seq 1 80); do
    printf '%s %s\n' "$(date +%s)" "$(http_code "http://${VIP}/sante")"
    sleep 0.25
  done
) > /tmp/v6.csv &
SONDE=$!

sleep 3
echo "-> vagrant halt lb1"
T_HALT=$(date +%s)
vagrant halt lb1
wait $SONDE

erreurs=$(awk '$2 != 200 { n++ } END { print n+0 }' /tmp/v6.csv)
premiere=$(awk '$2 == 200 && $1 > t { print $1; exit } { t = t ? t : $1 }' /tmp/v6.csv)
# reprise = première réponse 200 APRÈS l'arrêt de lb1
reprise=$(awk -v th="$T_HALT" '$2 == 200 && $1 >= th { print $1; exit }' /tmp/v6.csv)
if [ -n "$reprise" ]; then
  delai=$((reprise - T_HALT))
else
  delai=-1
fi

echo
echo "Réponses en erreur     : ${erreurs} (≠200)"
echo "Reprise de la VIP      : ${delai} s après l'arrêt (exigence < 5 s)"

echo "-> remise en service de lb1"
vagrant up lb1 >/dev/null

if [ "$delai" -ge 0 ] && [ "$delai" -lt 5 ]; then
  echo "RÉSULTAT V6 : OK"
else
  echo "RÉSULTAT V6 : À EXAMINER (délai=${delai}s, erreurs=${erreurs})"
  exit 1
fi
