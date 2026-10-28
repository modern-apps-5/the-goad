#!/usr/bin/env bash
# Print a Cloud Foundry access token for a Tanzu Hub OAuth app.
#
#   CF_CLIENT_ASSERTION=<the app's client assertion secret> token.sh <UAA token URL>
#
# The foundation's UAA takes only the app's client assertion secret, as
# private_key_jwt. The secret is key_ and then base64url text of JSON:
# oauthAppId, a JWT header (ES256, kid), privateKey (PEM, newlines written
# as \n) and an aud, which is Hub's issuer. The foundation refuses that
# aud: the JWT's aud must be its own token URL.
#
# Only bash, jq, openssl and curl, which the runner image has. The Tanzu cf
# CLI can do this login too, but on a fresh HOME it first installs about
# 140 MB of plugins.
set -euo pipefail

TOKEN_URL=${1:?usage: CF_CLIENT_ASSERTION=... $0 <UAA token URL>}
: "${CF_CLIENT_ASSERTION:?set CF_CLIENT_ASSERTION to the client assertion secret}"

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
umask 077

b64url() { openssl base64 -A | tr '+/' '-_' | tr -d '='; }
b64url_decode() {
  local s
  s=$(tr -d '\n' | tr '_-' '/+')
  case $((${#s} % 4)) in 2) s+="==" ;; 3) s+="=" ;; esac
  printf '%s' "$s" | openssl base64 -d -A
}

# The secret is "key_" then the base64url JSON.
printf '%s' "${CF_CLIENT_ASSERTION#key_}" | b64url_decode > "$work/secret.json"
client_id=$(jq -r .oauthAppId "$work/secret.json")
jq -r .privateKey "$work/secret.json" | sed 's/\\n/\n/g' > "$work/key.pem"

now=$(date +%s)
header=$(jq -c .header "$work/secret.json" | tr -d '\n' | b64url)
claims=$(jq -nc --arg id "$client_id" --arg aud "$TOKEN_URL" --arg jti "$(openssl rand -hex 16)" \
  --argjson now "$now" '{iss: $id, sub: $id, aud: $aud, jti: $jti, iat: $now, exp: ($now + 300)}' | tr -d '\n' | b64url)
printf '%s.%s' "$header" "$claims" > "$work/input"

# openssl signs ES256 as DER. A JWT wants r and s, 32 bytes each.
openssl dgst -sha256 -sign "$work/key.pem" -out "$work/sig.der" "$work/input"
raw=""
for int in $(openssl asn1parse -inform DER -in "$work/sig.der" | awk -F: '/INTEGER/ {print $NF}'); do
  int=$(printf '%064s' "${int#00}" | tr ' ' 0)
  raw+=${int: -64}
done
sig=$(printf '%s' "$raw" | sed 's/../\\x&/g' | xargs -0 printf '%b' | b64url)

curl -skf "$TOKEN_URL" \
  -H 'Accept: application/json' \
  --data-urlencode grant_type=client_credentials \
  --data-urlencode "client_id=$client_id" \
  --data-urlencode client_assertion_type=urn:ietf:params:oauth:client-assertion-type:jwt-bearer \
  --data-urlencode "client_assertion=$(cat "$work/input").$sig" \
  | jq -er .access_token
