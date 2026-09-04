# Load test log

_Appended by `tools/loadtest.py`. Each block names the host it ran against._

### burst: 16 simultaneous extract requests, no backoff, host http://127.0.0.1:8000
- status codes: {200: 2, 429: 14} (429 = refused immediately with Retry-After)
- served latency ms: p50 1761, max 1794; wall 1.8 s
- health during burst: HTTP 200, in_flight=0
- run at 2026-09-03 16:39:35

### steady: 40 x extract (1 image(s) each), concurrency 2, host http://127.0.0.1:8000
- wall 29.4 s, throughput 1.36 req/s (1.36 images/s)
- wall latency ms per successful request, including any backoff waits: p50 1464, p95 1537, max 1554
- final status codes: {200: 40}; 429 responses absorbed by backoff along the way: 0
- run at 2026-09-03 16:40:05

### steady: 20 x verify (2 image(s) each), concurrency 2, host http://127.0.0.1:8000
- wall 40.0 s, throughput 0.50 req/s (1.00 images/s)
- wall latency ms per successful request, including any backoff waits: p50 3988, p95 4161, max 4183
- final status codes: {200: 20}; 429 responses absorbed by backoff along the way: 0
- run at 2026-09-03 16:40:46

### steady: 20 x extract (1 image(s) each), concurrency 2, host http://127.0.0.1:8000
- wall 14.6 s, throughput 1.37 req/s (1.37 images/s)
- wall latency ms per successful request, including any backoff waits: p50 1451, p95 1505, max 1566
- final status codes: {200: 20}; 429 responses absorbed by backoff along the way: 0
- run at 2026-09-03 17:15:50

### steady interactive: 10 x verify (2 image(s) each), concurrency 2, host http://127.0.0.1:8000
- wall 19.6 s, throughput 0.51 req/s (1.02 images/s)
- wall latency ms per successful request, including any backoff waits: p50 3679, p95 4437, max 4631
- final status codes: {200: 10}; 429 responses absorbed by backoff along the way: 0
- run at 2026-09-03 17:16:10

