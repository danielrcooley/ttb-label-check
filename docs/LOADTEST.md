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

### steady: 300 x extract (1 image(s) each), concurrency 2, host http://127.0.0.1:8000
- wall 217.0 s, throughput 1.38 req/s (1.38 images/s)
- wall latency ms per successful request, including any backoff waits: p50 1447, p95 1495, max 1550
- final status codes: {200: 300}; 429 responses absorbed by backoff along the way: 0
- run at 2026-09-03 17:21:41

### browser batch: 150 applications x 2 images through the batch screen, host http://127.0.0.1:8000
- wall 275 s (1.09 images/s end to end, including compare calls and rendering)
- summary tiles: 120 Ready for approval | 30 Need review | 0 Issues / unreadable | 0 Errors | 0 Images not matched | 0/150 Decided | 2.0 s per image, median (p95 2.4 s)
- no browser errors
- run at 2026-09-03 17:26:18

### steady interactive: 20 x verify (2 image(s) each), concurrency 2, host https://label-check.proudmeadow-580dfc69.eastus.azurecontainerapps.io
- wall 52.3 s, throughput 0.38 req/s (0.77 images/s)
- wall latency ms per successful request, including any backoff waits: p50 4979, p95 5887, max 6987
- final status codes: {200: 20}; 429 responses absorbed by backoff along the way: 0
- run at 2026-09-03 20:00:51

### steady: 100 x extract (1 image(s) each), concurrency 2, host https://label-check.proudmeadow-580dfc69.eastus.azurecontainerapps.io
- wall 102.0 s, throughput 0.98 req/s (0.98 images/s)
- wall latency ms per successful request, including any backoff waits: p50 2016, p95 2238, max 2425
- final status codes: {200: 100}; 429 responses absorbed by backoff along the way: 0
- run at 2026-09-03 20:02:35

### burst: 16 simultaneous extract requests, no backoff, host https://label-check.proudmeadow-580dfc69.eastus.azurecontainerapps.io
- status codes: {429: 14, 200: 2} (429 = refused immediately with Retry-After)
- served latency ms: p50 4113, max 4172; wall 4.2 s
- health during burst: HTTP 200, in_flight=0
- run at 2026-09-03 20:02:39

### steady interactive: 20 x verify (2 image(s) each), concurrency 1, host https://label-check.proudmeadow-580dfc69.eastus.azurecontainerapps.io
- wall 61.8 s, throughput 0.32 req/s (0.65 images/s)
- wall latency ms per successful request, including any backoff waits: p50 3056, p95 3126, max 3718
- final status codes: {200: 20}; 429 responses absorbed by backoff along the way: 0
- run at 2026-09-03 20:05:15

### browser batch: 150 applications x 2 images through the batch screen, host https://label-check.proudmeadow-580dfc69.eastus.azurecontainerapps.io
- wall 364 s (0.82 images/s end to end, including compare calls and rendering)
- summary tiles: 150 Ready for approval | 0 Need review | 0 Issues / unreadable | 0 Errors | 0 Images not matched | 0/150 Decided | 2.7 s per image, median (p95 3.2 s)
- no browser errors
- run at 2026-09-03 20:11:24

## Build af9e239 on Azure (the unbounded sideways re-read, superseded by D-039)

The four runs below measured the build that re-read every image turned both ways, and large
artwork at full resolution, whenever no statement was found. A single-image extract, which is
how the batch screen reads, went from 2.0 s to 8.6 s and the 300-image batch from 364 s to
841 s. They are kept as the evidence for the bounded round; the runs after them are the
corrected build.

### steady interactive: 20 x verify (2 image(s) each), concurrency 2, host https://label-check.proudmeadow-580dfc69.eastus.azurecontainerapps.io
- wall 53.2 s, throughput 0.38 req/s (0.75 images/s)
- wall latency ms per successful request, including any backoff waits: p50 5127, p95 5890, max 6741
- final status codes: {200: 20}; 429 responses absorbed by backoff along the way: 0
- run at 2026-09-04 04:37:07

### steady: 100 x extract (1 image(s) each), concurrency 2, host https://label-check.proudmeadow-580dfc69.eastus.azurecontainerapps.io
- wall 432.7 s, throughput 0.23 req/s (0.23 images/s)
- wall latency ms per successful request, including any backoff waits: p50 8617, p95 8933, max 9191
- final status codes: {200: 100}; 429 responses absorbed by backoff along the way: 0
- run at 2026-09-04 04:44:20

### burst: 16 simultaneous extract requests, no backoff, host https://label-check.proudmeadow-580dfc69.eastus.azurecontainerapps.io
- status codes: {429: 14, 200: 2} (429 = refused immediately with Retry-After)
- served latency ms: p50 10184, max 10265; wall 10.3 s
- health during burst: HTTP 200, in_flight=0
- run at 2026-09-04 04:44:31

### browser batch: 150 applications x 2 images through the batch screen, host https://label-check.proudmeadow-580dfc69.eastus.azurecontainerapps.io
- wall 841 s (0.36 images/s end to end, including compare calls and rendering)
- summary tiles: 150 Ready for approval | 0 Need review | 0 Issues / unreadable | 0 Errors | 0 Images not matched | 0/150 Decided | 7.5 s per image, median (p95 8.7 s)
- no browser errors
- run at 2026-09-04 04:58:40

