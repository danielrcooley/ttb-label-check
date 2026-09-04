# Security and data handling

This is a prototype for a take-home exercise, deployed on a public URL with no authentication,
handling fictional sample data. The design still follows the rules that would apply to a real
deployment where they cost nothing, and it says plainly where it stops.

## Data handling

- **Nothing is stored.** Uploaded images are decoded in memory, read by the OCR engine, and
  discarded when the response is sent. There is no database, no upload directory, no cache of
  results. Batch state (files, results, decisions) lives only in the agent's browser tab.
- **Nothing sensitive is logged.** Request logs carry method, path, status and timing. Label text,
  filenames, application values and results never reach a log line.
- **Uploads stay in memory up to the per-image cap.** The web framework spools multipart parts above
  a threshold to a temporary directory while parsing; this app sets that threshold just above the
  10 MB per-image cap, so every accepted image stays in memory. A part larger than that is spooled
  to the container's temporary directory until the route rejects it: the local `docker run` recipe
  mounts `/tmp` in memory (`--tmpfs /tmp`); on Azure Container Apps it is the replica's ephemeral
  disk, discarded with the replica. Total memory is bounded by the 40 MB request cap times the
  global cap of 24 concurrent metered requests, which is enforced before parsing. Slow-client
  protection (a body that trickles in for minutes) is delegated to the platform ingress in front of
  the container, which enforces request timeouts; the container itself enforces the declared size
  and a 15-second keep-alive.
- **No outbound calls.** The verification path makes no network connections. OCR models are in
  the repository (hash-pinned in `app/models/MANIFEST.json`); frontend assets are self-hosted. A
  test blocks every socket connection and runs a full verification (`tests/integration/test_no_egress.py`).

## Controls in this build

| Control | Where |
|---|---|
| Request body size guard (declared length required, 40 MB cap) and per-image cap (10 MB) enforced while reading | `app/security.py`, `app/routes/api.py` |
| File type by signature, not extension; PDF, SVG, HEIC and unknown types refused with a specific message | `app/pipeline/images.py` |
| Decompression-bomb guard (25 megapixels, checked from the header before decoding; large JPEGs are decoded at reduced size) | `app/pipeline/images.py` |
| Corrupt or truncated images fail cleanly with an error envelope, never a stack trace | `app/pipeline/images.py`, `app/security.py` |
| Security headers: Content-Security-Policy (`default-src 'self'`, no inline scripts or styles), `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`, cross-origin isolation headers, `Cache-Control: no-store` | `app/security.py` |
| Per-client in-flight cap (4 concurrent requests) with 429 and Retry-After; global cap with 503 | `app/security.py` |
| Capacity limiter with interactive priority: batch never queues, it is refused with 429 when capacity is full or a person is waiting | `app/ocr/pool.py`, `tests/unit/test_pool.py` |
| Capacity is held for as long as an OCR thread actually runs, even if the client disconnects (inference cannot be interrupted, so freeing the slot early would oversubscribe the CPU) | `app/ocr/pool.py`, `tests/unit/test_pool.py` |
| Admission caps enforced in middleware before the request body is parsed: per client (4) and global (24 concurrent metered requests); `Server-Timing` on every response | `app/security.py` |
| Consistent error envelope `{code, message, hint, request_id}`; unhandled errors return a generic message and a request id | `app/security.py` |
| Container runs as a non-root user; only the runtime libraries the slim image needs | `Dockerfile` |
| No inline event handlers or `innerHTML` with user or OCR text; all text rendered via `textContent` | `app/static/*.js` |
| CSV export neutralizes spreadsheet formulas (`= + - @` prefixes) | `app/static/batch.js` |
| Direct dependencies pinned to exact versions; transitive ones are resolved at build time (no hash lock in this build, see below) | `requirements.txt`, `requirements-ocr.txt` |
| Dependency audit (`pip-audit`) on every CI run, advisory by design: a newly published advisory in a transitive package must not block a fix from shipping during the review window; findings are reviewed before release | `.github/workflows/ci.yml` |
| Nothing is published to the registry unless lint, types, unit and integration tests passed; CI runs are serialized per branch so an older image cannot overwrite `latest` | `.github/workflows/ci.yml` |
| Proxy trust is explicit: client identity from the LAST `X-Forwarded-For` value (the one the trusted ingress appends; the first can be forged) and only when `TTB_TRUST_PROXY=true` | `app/config.py`, `app/security.py` |

## Deliberately not in this build

- **Authentication and authorization.** There is no sign-in. A fake login page would demonstrate
  nothing. In production this sits behind the agency's identity provider: Entra ID single sign-on
  with PIV/CAC, enforced at the ingress (Azure Container Apps built-in authentication or an
  application gateway), with roles for agents and supervisors.
- **Audit trail.** Decisions are exported by the agent, not recorded by the server. A production
  version would write an append-only audit record of who checked what and decided what, which is
  also where the retention policy applies.
- **Rate limiting by identity.** Today the caps are per client address. With authentication they
  become per user.
- **Software bill of materials and hash-pinned installs.** Straightforward to add in CI
  (CycloneDX, `pip-compile --generate-hashes`); omitted from the prototype for time.

## Path to production (summary)

Azure Government region; private ingress with the identity provider in front; images and results
never leaving the agency boundary (they already never leave the container); a retention policy
for the audit record only; model files versioned and evaluated before each change; the same
container image promoted from test to production; monitoring on the health endpoint and the
`Server-Timing` header every response carries.

## Reporting a problem

Open an issue in the repository or contact the author. Do not include real label data in a report.
