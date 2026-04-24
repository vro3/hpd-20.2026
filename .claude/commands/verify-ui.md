---
description: Boot the HPD-20 web UI, smoke-test endpoints, open the browser
---

Kill any stale `hpd20-web` process, start a fresh server against `BKUP-021.HS0`, curl the critical endpoints, and open the browser. Report every endpoint's HTTP code inline.

```bash
pkill -f hpd20-web 2>/dev/null; sleep 1
.venv/bin/hpd20-web BKUP-021.HS0 > /tmp/hpd20-web.log 2>&1 &
sleep 2
curl -s -o /dev/null -w "GET /                         -> %{http_code}\n" http://127.0.0.1:8000/
curl -s -o /dev/null -w "GET /kit/4                    -> %{http_code}\n" http://127.0.0.1:8000/kit/4
curl -s -o /dev/null -w "GET /kit/4/pad/0 (HTMX)       -> %{http_code}\n" -H 'HX-Request: true' http://127.0.0.1:8000/kit/4/pad/0
curl -s -o /dev/null -w "GET /api/instruments          -> %{http_code}\n" http://127.0.0.1:8000/api/instruments
curl -s -o /dev/null -w "GET /api/midi/devices         -> %{http_code}\n" http://127.0.0.1:8000/api/midi/devices
curl -s -o /dev/null -w "GET /api/midi/pad-lookup/4    -> %{http_code}\n" http://127.0.0.1:8000/api/midi/pad-lookup/4
open http://127.0.0.1:8000/
```

If any endpoint is not 200, tail `/tmp/hpd20-web.log` for the error and report what broke. To stop the server later: `pkill -f hpd20-web`.
