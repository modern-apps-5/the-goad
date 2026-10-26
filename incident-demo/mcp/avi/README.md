# Avi MCP

Standalone controller door for this demo. It is not vcf-mcp.

It listens on `127.0.0.1:8093` and exposes five read-only tools:
`avi_vs_health`, `avi_pool_member_health`, `avi_latency`,
`avi_error_rates`, and `avi_se_state`.

Set `AVI_CONTROLLER`. Leave `AVI_PASSWORD` empty to fetch the
controller admin password from SDDC Manager (`resourceType` `NSX_ALB`)
at login. The password is not written here.

```bash
cd avi-mcp
AVI_MCP_ENV=/path/to/avi-mcp.env python3 server.py
```

`GET /health` reports whether the process has a controller session.
