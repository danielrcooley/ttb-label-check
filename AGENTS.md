# Conventions for agents working in this repository

This codebase is developed by a human directing AI coding agents (Claude Code as builder,
Codex as reviewer). These conventions keep that workflow safe and legible. `CLAUDE.md` points here.

## Roles
- **Builder** writes application code, tests, docs. One builder at a time.
- **Reviewer** reads and reports. Reviewers write only under `docs/reviews/` and
  `tools/adversarial/`. Reviewers never edit application code directly; findings are filed and
  the builder acts on them.
- **Human** decides scope, approves deploys, and owns every decision in `docs/DECISIONS.md`.

## Non-negotiable rules (all enforced by tests where possible)
1. **No outbound network calls in the verification path.** OCR runs in-process. Models are baked
   into the image at build time. `tests/test_no_egress.py` blocks sockets and must stay green.
2. **Nothing is stored.** No database, no upload directory, no logging of label text, filenames,
   or application data. Images live in memory for the duration of one request.
3. **The tool recommends; the agent decides.** No code path approves or rejects an application.
   Statuses are Match / Needs review / Mismatch / Not found; verdicts are recommendations.
4. **Heuristic findings are never failures.** Caps, bold, size, contrast, standards of fill,
   inferred beverage type: report Needs review with evidence. Only clear text or numeric
   mismatches are Mismatch.
5. **No external assets in the frontend.** No CDN scripts, fonts, or styles. Everything is
   served from `app/static/`.
6. **No official seals or government branding.** The header shows a prototype banner. The
   `AGENCY_NAME` / `AGENCY_LOGO` slot is for internal deployment by the agency, not for us.
7. **Every response is deterministic** for the same input and model version. No sampling
   anywhere in the core path.

## Layout
```
app/            FastAPI application (routes/, ocr/, pipeline/, static/)
tests/          unit/ (fast, no OCR)  integration/ (OCR on fixtures)  fixtures/ (committed PNGs)
tools/          make_labels.py  bakeoff.py  ocr_perf.py  loadtest.py  evaluate.py
docs/           APPROACH.md  REQUIREMENTS_TRACE.md  LIMITS.md  SECURITY.md  DECISIONS.md
                PROCESS.md  REGULATIONS.md  BAKEOFF.md  reviews/  regs/
samples/        bundled demo labels + sample CSV (fictional brands only)
```

## Commands
```
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt -r requirements-dev.txt
.venv/Scripts/pip install --no-deps -r requirements-ocr.txt   # never let rapidocr pull desktop opencv-python
uvicorn app.main:app --reload            # run locally on :8000
pytest -m "not integration and not slow" # fast tests
pytest                                    # everything
ruff check . && ruff format --check . && mypy
python tools/make_labels.py --out tests/fixtures/labels --seed 42 --degraded --problems
python tools/evaluate.py                  # accuracy + latency table
python tools/loadtest.py --url http://localhost:8000 --n 200 --concurrency 8
docker build -t ttb-label-check . && docker run --rm -p 8000:8000 --network none ttb-label-check
```

## Style
- Python 3.12+, type hints everywhere, `mypy --strict` clean. Pydantic models for every request
  and response. Small pure functions in `app/pipeline/`; I/O only in `app/routes/`.
- Frontend: vanilla ES modules, JSDoc types, no build step. Text from users or OCR is rendered
  with `textContent`, never `innerHTML`.
- Tests name the behavior: `test_case_only_difference_is_match_with_note`.
- Docs are plain language. English docs use spaced hyphens, no em-dashes.
- Commits: small, imperative, descriptive. No "wip". Builder commits carry the agent trailer.

## Definition of Done for a change
Tests added or updated, fast suite green, `ruff` and `mypy` clean, docs touched if behavior
changed, `docs/DECISIONS.md` updated if a decision was made, and the deployed URL still works.
