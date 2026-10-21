# Tanzu demo — Presidio PII on the AI Services tile

The talk apps do **not** filter chat. The **AI Services** (`genai`)
tile does. Policy handle `presidio-content-filter` POSTs each chat
turn to this app. Microsoft Presidio replaces names, emails, phones,
US SSNs, cards, IPs, and driver-license numbers before Qwen sees
them, and again on the model reply.

This app does not print a company name.

## Contract (tile 10.4.3 / ai-server 0.81.0)

Chat Base URL: `https://pii-scrub.${TANZU_APPS_DOMAIN}`

| Path | Tile posts | We return |
|---|---|---|
| `POST /prompt` | OpenAI chat request | same object, strings scrubbed |
| `POST /response` | OpenAI chat completion | same object, strings scrubbed |
| `POST /response/stream` | OpenAI chunk | same object, strings scrubbed |
| `GET /health` | — | `{"status":"ok","engine":"presidio"}` |

A **404** on a path the tile does not need is skipped
(`HttpClientErrorException.NotFound`). Any other 4xx/5xx fails the
chat request. Unused embedding paths stay 404 on purpose.

The tile Java client POSTs **chunked** bodies with no
Content-Length. The app must read `Transfer-Encoding: chunked`.
If it only honors Content-Length it returns `{}` and the model
sees an empty turn.

Bodies are PII. Logs record method and path only.

Stream chunks are short. Regex entities (email, phone, SSN, card)
still match when the whole pattern is in one chunk. A name split
across chunks may pass. The demo moment is `/prompt`: the whole
user turn arrives at once.

## Rebuild

1. Unit tests (no spaCy):

   ```bash
   python3 -m unittest tests.test_tanzu_pii
   ```

The spaCy English **small** model wheel lives in `wheels/` so Diego
does not need GitHub at stage time. `scrub.py` pins
`en_core_web_sm` through Presidio's `NlpEngineProvider`. The
default AnalyzerEngine would download `en_core_web_lg` (~400MB)
on first boot and die on a 512M cell.

Do not put other packages in a `vendor/` folder — the Python
buildpack then goes offline-only and staging fails.

2. Push the webhook (org Goad / space ${GOAD_VCFA_SPACE}):

   ```bash
   ./departments/it/tanzu-pii/push.sh
   ```

3. Tile overlay lives in the lab repo
   `config/tanzu/genai/openai-compatible-spark1.yml`.
   It sets `.controller.policy_web_hooks` and puts
   `presidio-content-filter` on plan `spark1-qwen-122b`.

   ```bash
   set -a && source ~/secrets/opsman.env && set +a
   unset OM_CLIENT_ID OM_CLIENT_SECRET
   cd /home/cursor/code/vcf-lab
   om configure-product -p genai -c config/tanzu/genai/openai-compatible-spark1.yml
   om apply-changes --product-name genai --ignore-warnings
   ```

   Scoped **genai only**. Do not full-foundation Apply.
   `release-tests` stays off. Profile `experimental-webhook` is
   already in the tile default `active_profiles`.

4. Prove the door, not the talk UI:

   ```bash
   ./departments/it/tanzu-pii/verify.sh
   ```

Then in a talk tab type a made-up email. The model should see
`[EMAIL]`, not the address. A 7-digit phone becomes `[PHONE]`,
a Luhn card `[CARD]`, a dashed SSN `[SSN]`, and a name
`[NAME]` only when that same text already has one of those.
Presidio does not print “blocked.” Do not paste real people.

The bubble is a different door. The tile response call does
not contain the reply, so this webhook cannot change it.
`chatguard/` answers `POST /api/chat` on the incident host
when the message has an email, phone, card, or SSN. The
reply is the fixed guardrail line plus the masked complaint,
and the model is not called. Enrichment is proxied to
`incident-response-agent-origin`. Push that app with
`./departments/it/tanzu-pii/chatguard/push.sh` (space
`${GOAD_VCFA_SPACE}`). Map the path only after
`/ready` says the origin is ok:

```bash
cf map-route pii-chat-guard ${TANZU_APPS_DOMAIN} \
  --hostname incident-response-agent --path api/chat
```

Rollback, which leaves the agent droplet alone:

```bash
cf unmap-route pii-chat-guard ${TANZU_APPS_DOMAIN} \
  --hostname incident-response-agent --path api/chat
```

`/prompt` also sets `reasoning_effort` to `none` so Qwen does
not spend the turn thinking. That thinking-only reply was the
“history must end with a ModelRequest” failure on the VCF,
load balancer, and Kubernetes agents. How to turn the filter
or change entities: `docs/products/tanzu-ai-pii.md`.

If talk goes red at about 60 seconds with
`incomplete chunked read` or `OpenAIIoException`, that is
Qwen still finishing a Paperclip job. Check
`http://${LAB_NET_192_168_2_29}:11434/proxy/slot`. It is not a dead
webhook. Ask again once holder is not `bulk`.

## Diego

`pii-scrub` is **512M / 2G disk** (1G did not fit the Diego
cell). Health invocation is **10s** — Presidio+spaCy boot
misses the default 1s liveness (same miss as `k8s-mcp`). Pin
it in `departments/it/demo-fleet.json`. Do not stop it to
free a cell during a walk.

## Official docs

- Policies (webhook technical preview): Broadcom AI Services 10.4
  *Configure Policies* — handle example is `presidio-content-filter`
- Presidio: Microsoft analyzer + anonymizer, spaCy `en_core_web_sm`
