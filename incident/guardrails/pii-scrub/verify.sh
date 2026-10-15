#!/usr/bin/env bash
# Prove the webhook door. Uses made-up example.com PII only.
set -euo pipefail
BASE="${PII_SCRUB_URL:-https://pii-scrub.${TANZU_APPS_DOMAIN}}"
code=$(curl -sk -o /tmp/pii-scrub-health.json -w '%{http_code}' "${BASE}/health")
echo "health ${code}"
test "${code}" = "200"
python3 - <<'PY' "${BASE}"
import json, sys, urllib.request
base = sys.argv[1]
body = {
    "model": "gpt-oss:120b",
    "messages": [
        {"role": "user", "content": "My name is Casey Nguyen. Email jane.doe@example.com. Call 555-0100. SSN 457-55-5462."}
    ],
}
req = urllib.request.Request(
    base + "/prompt",
    data=json.dumps(body).encode(),
    method="POST",
    headers={"Content-Type": "application/json"},
)
ctx = None
import ssl
ctx = ssl._create_unverified_context()
with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
    out = json.loads(resp.read().decode())
text = out["messages"][0]["content"]
email_gone = "jane.doe@example.com" not in text
ssn_gone = "457-55-5462" not in text
phone_gone = "555-0100" not in text
name_gone = "Casey Nguyen" not in text
ok = (
    email_gone and ssn_gone and phone_gone and name_gone
    and "[EMAIL]" in text and "[SSN]" in text and "[PHONE]" in text and "[NAME]" in text
)
print("prompt-scrub", "ok" if ok else "FAIL")
print("email-gone", email_gone, "ssn-gone", ssn_gone, "phone-gone", phone_gone, "name-gone", name_gone)
print("tokens", "[EMAIL]" in text, "[PHONE]" in text, "[CARD]" in text, "[SSN]" in text, "[NAME]" in text)
print("shape-kept", out.get("model") == "gpt-oss:120b")
print("reasoning-off", out.get("reasoning_effort") == "none")
if not ok or out.get("reasoning_effort") != "none":
    raise SystemExit("PII still in /prompt body")
PY
echo "webhook door ok"
