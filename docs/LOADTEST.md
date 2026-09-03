# Load test log

_Appended by `tools/loadtest.py`. Each block names the host it ran against._

### burst: 16 simultaneous extract requests, no backoff, host http://127.0.0.1:8000
- status codes: {200: 2, 429: 14} (429 = refused immediately with Retry-After)
- served latency ms: p50 1483, max 1526; wall 1.5 s
- health during burst: HTTP 200, in_flight=0
- run at 2026-09-03 16:25:48

### steady: 40 x extract (1 image(s) each), concurrency 4, host http://127.0.0.1:8000
- wall 26.8 s, throughput 1.49 req/s (1.49 images/s)
- latency ms (successful): p50 1451, p95 1534, max 6531
- status codes: {200: 36, 429: 4}; 429s absorbed by backoff: 40
- run at 2026-09-03 16:26:15

### steady: 20 x verify (2 image(s) each), concurrency 2, host http://127.0.0.1:8000
- wall 95.7 s, throughput 0.21 req/s (0.42 images/s)
- latency ms (successful): p50 2387, p95 2387, max 8729
- status codes: {200: 3, 429: 17}; 429s absorbed by backoff: 141
- run at 2026-09-03 16:27:51

