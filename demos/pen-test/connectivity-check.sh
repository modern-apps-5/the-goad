#!/usr/bin/env bash
# Runs inside the attacker pod in namespace music-store (attacker.yaml).
# Tries to reach the shop's front end five ways and prints the HTTP code
# and a pass or fail for each:
#
#   1  the store pod's IP        around the Service and Avi
#   2  the store's Service name  around Avi
#   3  through Avi, SQL injection   the WAF must answer 403
#   4  through Avi, PHP injection   the WAF must answer 403
#   5  through Avi, clean request   200
#
# 1 and 2 must get no answer: the platform engineer's default deny drops
# them, so the only way in is through the Avi WAF (decision 49). Without
# the policy and the L7Rule all five answer 200.
#
# Every setting has a default for this lab and can be overridden per run:
#   VIP=10.47.7.95 /scripts/connectivity-check.sh
set -u

HOST=${HOST:-music.goad.gpu.set.lab}
# The Gateway's address. Empty: resolve HOST through DNS.
VIP=${VIP:-}
SVC=${SVC:-http://music-store-1-service.music-store.svc.cluster.local:5000}
TGT_NS=${TGT_NS:-music-store}
TGT_LABEL=${TGT_LABEL:-service-name=store}
PORT=${PORT:-5000}
SQLI=${SQLI:-?searchString=%27%20OR%201%3D1--}
PHPI=${PHPI:-?file=php%3A%2F%2Ffilter%2Fconvert.base64-encode%2Fresource%3Dindex.php}
TIMEOUT=${TIMEOUT:-5}

URL=https://$HOST
RESOLVE=()
[ -n "$VIP" ] && RESOLVE=(--resolve "$HOST:443:$VIP")

if [ -t 1 ]; then
  B=$'\e[1m' C=$'\e[36m' G=$'\e[32m' RED=$'\e[31m' Y=$'\e[33m' N=$'\e[0m'
else
  B= C= G= RED= Y= N=
fi

rule() { echo "${B}${C}----------------------------------------------------------------${N}"; }
title() { echo; rule; echo "${B}${C}  $*${N}"; rule; }

# probe [--deny | --expect CODE] <label> <note> <curl args...>
#   --deny         no answer is the pass; any HTTP answer is a fail.
#   --expect CODE  only HTTP CODE is the pass.
probe() {
  local deny=0 expect=""
  while :; do
    case "$1" in
      --deny) deny=1; shift ;;
      --expect) expect=$2; shift 2 ;;
      *) break ;;
    esac
  done
  local label=$1 note=$2; shift 2
  echo
  echo "${B}== ${label}${N}"
  echo "   ${Y}expect: ${note}${N}"
  echo "   ${B}\$ curl $*${N}"
  local out
  if ! out=$(curl -k -s -o /dev/null -w '%{http_code}' --max-time "$TIMEOUT" "$@"); then
    if [ "$deny" -eq 1 ]; then
      echo "   ${G}PASS: no answer, the traffic was dropped${N}"
    else
      echo "   ${RED}FAIL: no answer${N}"
    fi
  elif [ "$deny" -eq 1 ]; then
    echo "   ${RED}FAIL: HTTP ${out}, the traffic was not dropped${N}"
  elif [ "$out" = "$expect" ]; then
    echo "   ${G}PASS: HTTP ${out}${N}"
  else
    echo "   ${RED}FAIL: HTTP ${out}, expected ${expect}${N}"
  fi
}

title "Target"
echo "   namespace : ${TGT_NS}"
echo "   label     : ${TGT_LABEL}"
IP=$(kubectl -n "$TGT_NS" get pod -l "$TGT_LABEL" -o jsonpath='{.items[0].status.podIP}' 2>/dev/null)
echo "   pod IP    : ${IP:-${Y}not found (label, or the Role in attacker.yaml)${N}}"
echo "   address   : ${VIP:-DNS}"

title "1) The store pod's IP, around the Service and Avi"
if [ -n "$IP" ]; then
  probe --deny "pod ${IP}:${PORT}" "no answer, dropped by the default deny" "http://${IP}:${PORT}/"
else
  echo "   ${Y}skipped, no pod IP${N}"
fi

title "2) The store's Service, around Avi"
probe --deny "service ${SVC}" "no answer, dropped by the default deny" "${SVC}/"

title "3) Through Avi, SQL injection"
probe --expect 403 "GET ${URL}/${SQLI}" "HTTP 403 from the Avi WAF" "${RESOLVE[@]}" "${URL}/${SQLI}"

title "4) Through Avi, PHP injection"
probe --expect 403 "GET ${URL}/${PHPI}" "HTTP 403 from the Avi WAF" "${RESOLVE[@]}" "${URL}/${PHPI}"

title "5) Through Avi, clean request"
probe --expect 200 "GET ${URL}/" "HTTP 200" "${RESOLVE[@]}" "${URL}/"
