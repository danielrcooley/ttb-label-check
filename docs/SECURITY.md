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
- **Uploads stay in memory.** The web framework normally spools multipart parts above 1 MB to a
  temporary directory while parsing; this app raises that threshold above the per-image cap, so
  images are never written to disk. Total memory is bounded by the request-size cap times the
  number of concurrent requests. Mounting `/tmp` in memory (`docker run --tmpfs /tmp`) remains good
  hygiene as a second line of defense.
- **No outbound calls.** The verification path makes no network connections. OCR models are in
  the repository (hash-pinned in `app/models/MANIFEST.json`); frontend assets are self-hosted. A
  test blocks every socket connection and runs a full verification (`tests/integration/test_no_egress.py`).

## Controls in this build

| Control | Where |
|---|---|
| Request body size guard (declared length required, 40 MB cap) and per-image cap (10 MB) enforced while reading | `app/security.py`, `app/routes/api.py` |
| File type by signature, not extension; PDF, SVG, HEIC and unknown types refused with a specific message | `app/pipeline/images.py` |
| Decompression-bomb guard (40 megapixels, checked from the header before decoding) | `app/pipeline/images.py` |
| Corrupt or truncated images fail cleanly with an error envelope, never a stack trace | `app/pipeline/images.py`, `app/security.py` |
| Security headers: Content-Security-Policy (`default-src 'self'`, no inline scripts or styles), `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`, cross-origin isolation headers, `Cache-Control: no-store` | `app/security.py` |
| Per-client in-flight cap (4 concurrent requests) with 429 and Retry-After | `app/security.py` |
| Capacity limiter with interactive priority: batch never queues, it is refused with 429 when capacity is full or a person is waiting | `app/ocr/pool.py`, `tests/unit/test_pool.py` |
| Cooperative time budgets: no pretend cancellation of running inference | `app/services.py` |
| Consistent error envelope `{code, message, hint, request_id}`; unhandled errors return a generic message and a request id | `app/security.py` |
| Container runs as a non-root user; only the runtime libraries the slim image needs | `Dockerfile` |
| No inline event handlers or `innerHTML` with user or OCR text; all text rendered via `textContent` | `app/static/*.js` |
| CSV export neutralizes spreadsheet formulas (`= + - @` prefixes) | `app/static/batch.js` |
| Dependencies pinned to exact versions | `requirements.txt` |
| Proxy trust is explicit: client identity from `X-Forwarded-For` only when `TTB_TRUST_PROXY=true` | `app/config.py`, `app/security.py` |

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
per-request timing header.

## Reporting a problem

Open an issue in the repository or contact the author. Do not include real label data in a report.
