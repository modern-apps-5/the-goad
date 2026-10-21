# Grafana boards for the Goad incident demo

Nothing in this directory is installed by this pull request. Namespace `grafana` on cluster `goad-store` comes later.

| File | Board |
|---|---|
| `incident-live.json` | Incident live |
| `can-i-demo-right-now.json` | Can I demo right now? |
| `dgx-spark1.json` | spark1, retargeted to the Ollama VM `goad-qwen` |
| `alerts.yaml` | in-flight and host-memory alerts, no contact point |
| `datasource.yaml` | Prometheus uid `goad-prometheus` |

Goad has no GPU. The spark1 GPU panels are text that says `no GPU`. They do not query a GPU exporter and they do not show a zero.

Demo-ready, in flight, queue, latency, and the loaded-model panel read these series once a scraper exists. They are not published in this pull request:

- `ollama_demo_ready`
- `ollama_demo_ready_info`
- `ollama_slot_busy`
- `ollama_queue_depth`
- `ollama_inflight_seconds`
- `ollama_request_latency_seconds`
- `ollama_request_latency_samples`
- `ollama_model_resident_bytes{model="qwen2.5:32b"}`
- `ollama_host_memory_used_ratio`

Can I demo right now? is true only when Ollama answers, `qwen2.5:32b` is loaded, nothing is in flight, the queue is empty, the store is HTTP 200, Zammad is HTTP 200, and AgentMinder discovery is HTTP 200. The board still reads `/api/captain/demo-ready`. Company efficiency is not in this package.
