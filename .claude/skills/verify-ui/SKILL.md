---
name: verify-ui
description: Boot the HPD-20 web UI against BKUP-021.HS0, smoke-test the key endpoints, and open the browser. Use when the user says "run it", "let me see", "show me", or otherwise wants a live demo of the current state.
disable-model-invocation: true
---

# Verify UI

Kills any stale `hpd20-web` process, boots a fresh one against
`BKUP-021.HS0`, curls a handful of critical endpoints for HTTP 200s, then
opens the editor in the browser.

## Procedure

```bash
# 1. Tear down any stale server from an earlier session
pkill -f hpd20-web 2>/dev/null; sleep 1

# 2. Boot fresh
.venv/bin/hpd20-web BKUP-021.HS0 > /tmp/hpd20-web.log 2>&1 &
sleep 2

# 3. Smoke-test the critical endpoints
curl -s -o /dev/null -w "GET /                         -> %{http_code}\n" http://127.0.0.1:8000/
curl -s -o /dev/null -w "GET /kit/4                    -> %{http_code}\n" http://127.0.0.1:8000/kit/4
curl -s -o /dev/null -w "GET /kit/4/pad/0              -> %{http_code}\n" -H 'HX-Request: true' http://127.0.0.1:8000/kit/4/pad/0
curl -s -o /dev/null -w "GET /api/instruments          -> %{http_code}\n" http://127.0.0.1:8000/api/instruments
curl -s -o /dev/null -w "GET /api/midi/devices         -> %{http_code}\n" http://127.0.0.1:8000/api/midi/devices
curl -s -o /dev/null -w "GET /api/midi/pad-lookup/4    -> %{http_code}\n" http://127.0.0.1:8000/api/midi/pad-lookup/4

# 4. Open browser
open http://127.0.0.1:8000/
```

Report each endpoint's status inline (expect all 200s). If any is not 200,
tail `/tmp/hpd20-web.log` for the error and report what broke.

To stop the server later: `pkill -f hpd20-web`.
