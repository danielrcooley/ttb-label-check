// Batch screen. The browser orchestrates: every image is read once (/extract), images are paired
// to application rows explicitly (CSV "images" column or filename prefix), each application is
// compared (/compare), rows stream into the table, the agent records decisions, and everything can
// be exported. The server stays stateless; a refresh clears the session and the page says so.
import { ApiError, compare, extract, health } from "./api.js";
import { drawOverlays, el, makeCrops, renderChecklist, renderFigures, renderWarning, statusTag } from "./render.js";

const VERDICT_WORD = { ready_for_approval: "Ready", needs_review: "Needs review", issues_found: "Issues found", unreadable: "Unreadable" };
const VERDICT_STATUS = { ready_for_approval: "match", needs_review: "needs_review", issues_found: "mismatch", unreadable: "not_found" };
const SEVERITY = { issues_found: 0, unreadable: 1, needs_review: 2, ready_for_approval: 3 };
const PAGE_SIZE = 50;
const ACCEPT = /^image\/(png|jpeg|gif|webp|tiff|bmp)$/;
const $ = (sel) => document.querySelector(sel);

const state = {
  images: new Map(),      // fileKey (relative path or name, lower-cased) -> File
  inputVersion: 0, builtVersion: -1, detailCache: new Map(),
  csv: null,              // parsed CSV response
  items: [],              // application rows (or one per image when there is no CSV)
  unpaired: [],           // file names not attached to any row
  extractions: new Map(), // file name -> extract response
  decisions: new Map(),   // item key -> {decision, note}
  running: false, abort: null, maxConcurrency: 3, concurrency: 3, successes: 0, inflight: 0, waiters: [], renderTimer: 0,
  filter: "all", page: 0, expanded: null, times: [], startedAt: 0,
};

// ------------------------------------------------------------------ helpers
const norm = (name) => name.split(/[\\/]/).pop().toLowerCase();          // basename, lower-cased
const stem = (name) => norm(name).replace(/\.[a-z0-9]+$/, "");
const fileKey = (f) => (f.webkitRelativePath || f.name).toLowerCase();  // folder-aware identity
function setStatus(text, busy = false) { const s = $("#batch-status"); s.textContent = text; s.classList.toggle("is-busy", busy); }
function showError(msg) { const box = $("#batch-error"); box.querySelector("p").textContent = msg; box.hidden = !msg; }
function seconds(ms) { return `${(ms / 1000).toFixed(1)} s`; }
function percentile(arr, p) { if (!arr.length) return 0; const s = [...arr].sort((a, b) => a - b); return s[Math.min(s.length - 1, Math.floor(p * s.length))]; }

// ------------------------------------------------------------------ intake
function addImages(files) {
  let added = 0;
  for (const f of files) {
    if (f.type && !ACCEPT.test(f.type)) continue;
    if (f.size === 0 || f.size > 10 * 1024 * 1024) continue;
    const key = fileKey(f);
    if (!state.images.has(key)) { state.images.set(key, f); added++; }
  }
  state.inputVersion++;
  const byName = new Map();
  for (const k of state.images.keys()) byName.set(norm(k), (byName.get(norm(k)) || 0) + 1);
  const dupes = [...byName.entries()].filter(([, n]) => n > 1);
  let msg = `${state.images.size} image${state.images.size === 1 ? "" : "s"} ready${added ? ` (${added} added)` : ""}.`;
  if (dupes.length) msg += ` ${dupes.length} file name${dupes.length === 1 ? "" : "s"} appear${dupes.length === 1 ? "s" : ""} in more than one folder (${dupes.slice(0, 3).map(([n]) => n).join(", ")}${dupes.length > 3 ? ", …" : ""}); those are kept apart and cannot be paired by name alone.`;
  $("#batch-image-count").textContent = msg;
  updateStartButton();
}

async function setCsv(file) {
  const fd = new FormData();
  fd.append("file", file, file.name);
  const box = $("#batch-csv-summary");
  try {
    const resp = await fetch("/api/v1/csv/parse", { method: "POST", body: fd });
    const body = await resp.json();
    if (!resp.ok) throw new ApiError(resp.status, body);
    state.csv = body;
    state.inputVersion++;
    const bad = body.rows.filter((r) => r.errors.length);
    box.replaceChildren(...[
      el("p", { class: "text-bold margin-0", text: `${file.name}: ${body.rows.length} row${body.rows.length === 1 ? "" : "s"}${bad.length ? `, ${bad.length} with problems` : ""}.` }),
      body.warnings.length ? el("ul", { class: "usa-list usa-list--unstyled text-secondary-dark" }, body.warnings.map((w) => el("li", { text: w }))) : null,
      bad.length ? el("details", {}, [el("summary", { text: "Rows with problems (they will be skipped)" }),
        el("ul", { class: "usa-list" }, bad.slice(0, 20).map((r) => el("li", { text: `Row ${r.row_number}: ${r.errors.join("; ")}` })))]) : null,
    ].filter(Boolean));
  } catch (e) {
    state.csv = null;
    state.inputVersion++; // a failed replacement still changes the inputs: items must be rebuilt
    box.replaceChildren(el("p", { class: "text-secondary-dark text-bold", text: e.message || "Could not read the CSV." }));
  }
  updateStartButton();
}

function updateStartButton() {
  $("#batch-start").disabled = state.running || state.images.size === 0;
}

// ------------------------------------------------------------------ pairing (explicit only)
function buildItems() {
  if (state.items.length && state.builtVersion !== state.inputVersion) {
    state.decisions.clear(); // decisions were made against the previous images or spreadsheet
    state.times = [];
  }
  const files = new Map(state.images);       // copy; we remove as we attach
  const items = [];
  if (state.csv) {
    for (const row of state.csv.rows) {
      if (!row.application) continue;
      const app = row.application;
      const key = app.application_id || `row-${row.row_number}`;
      const slash = (s) => s.toLowerCase().replace(/\\/g, "/");
      const byName = (n) => [...files.keys()].filter((k) => norm(k) === norm(n));
      // A relative path in the CSV ("folder-a/back.png") matches the file's path (which may start with
      // the picked folder's own name) before falling back to the bare file name.
      const byPath = (n) => { const p = slash(n); return [...files.keys()].filter((k) => slash(k) === p || slash(k).endsWith("/" + p)); };
      let keys = [];
      const missing = [];
      for (const listed of row.images) {
        const exact = byPath(listed);
        const hits = exact.length ? exact : byName(listed);
        if (hits.length === 1) keys.push(hits[0]);
        else missing.push(hits.length ? `${listed} (ambiguous: ${hits.length} files)` : listed);
      }
      let method = row.images.length ? (missing.length ? `listed in CSV (${missing.length} not found)` : "listed in CSV") : "none";
      if (!row.images.length && app.application_id) {
        const id = app.application_id.toLowerCase();
        keys = [...files.keys()].filter((k) => { const st = stem(k); return st === id || st.startsWith(id + "_") || st.startsWith(id + "-") || st.startsWith(id + " "); });
        method = keys.length ? "filename prefix" : "none";
      }
      const attached = keys.map((k) => files.get(k)).filter(Boolean);
      for (const k of keys) files.delete(k);
      items.push({ key, row: row.row_number, application: app, files: attached, missing, method,
        result: null, error: null, ms: 0, status: attached.length ? "pending" : "no-images" });
    }
    state.unpaired = [...files.keys()];
  } else {
    for (const [n, f] of files) {
      items.push({ key: n, row: null, application: null, files: [f], missing: [], method: "extract only", result: null, error: null, ms: 0, status: "pending" });
    }
    state.unpaired = [];
  }
  state.items = items;
  state.builtVersion = state.inputVersion;
  state.detailCache.clear();
}

// ------------------------------------------------------------------ processing
// Request-level limiter: at most state.concurrency extract calls in flight, whatever the number of
// applications being worked on. Adaptive: shrinks on 429, grows back slowly after successes.
function acquireSlot() {
  if (state.inflight < state.concurrency) { state.inflight++; return Promise.resolve(); }
  return new Promise((resolve) => state.waiters.push(resolve));
}
function releaseSlot() {
  if (state.waiters.length && state.inflight <= state.concurrency) { state.waiters.shift()(); return; }
  state.inflight--;
}

async function extractOne(file, signal) {
  const key = fileKey(file);
  if (state.extractions.has(key)) return state.extractions.get(key);
  let delay = 0;
  for (let attempt = 0; attempt < 6; attempt++) {
    if (delay) { await new Promise((r) => setTimeout(r, delay)); delay = 0; } // back off without holding a slot
    await acquireSlot();
    try {
      const t0 = performance.now();
      const res = await extract([file], { batch: true, signal });
      state.times.push(performance.now() - t0);
      state.extractions.set(key, res);
      state.successes++;
      if (state.successes % 20 === 0 && state.concurrency < state.maxConcurrency) state.concurrency++;
      return res;
    } catch (e) {
      if (e.name === "AbortError") throw e;
      if (e instanceof ApiError && (e.status === 429 || e.status === 503)) {
        state.concurrency = Math.max(1, state.concurrency - 1);
        delay = (e.retryAfter || 1) * 1000 * (attempt + 1) + Math.random() * 500;
        continue;
      }
      throw e;
    } finally {
      releaseSlot();
    }
  }
  throw new ApiError(429, { message: "The service stayed busy; this item was skipped. Resume to try again." });
}

function linesForItem(item) {
  const lines = [], images = [];
  item.files.forEach((f, idx) => {
    const ex = state.extractions.get(fileKey(f));
    if (!ex) return;
    for (const im of ex.images) images.push({ ...im, index: idx });
    for (const ln of ex.lines) lines.push({ ...ln, image_index: idx });
  });
  return { lines, images };
}

async function processItem(item, signal) {
  item.status = "working";
  const t0 = performance.now();
  try {
    await Promise.all(item.files.map((f) => extractOne(f, signal)));
    const { lines, images } = linesForItem(item);
    if (item.application) {
      const resp = await compare([{ item_id: item.key, application: item.application, lines, images }], { signal });
      item.result = resp.results[0];
      item.lines = lines;
      item.images = images;
    } else {
      const ex = state.extractions.get(fileKey(item.files[0]));
      item.result = null;
      item.fields = ex.fields;
      item.lines = lines;
      item.images = images;
    }
    item.status = "done";
  } catch (e) {
    if (e.name === "AbortError") { item.status = "pending"; return; }
    item.status = "error";
    item.error = e instanceof ApiError ? `${e.message}${e.hint ? " " + e.hint : ""}` : "Network error.";
  } finally {
    item.ms = Math.round(performance.now() - t0);
  }
}

function scheduleRender() {
  if (state.renderTimer) return;
  state.renderTimer = setTimeout(() => { state.renderTimer = 0; renderProgress(); renderTable(); }, 250);
}

async function runPool(items, signal) {
  const queue = [...items];
  let active = 0;
  await new Promise((resolve) => {
    const pump = () => {
      if (signal.aborted && active === 0) return resolve();
      while (!signal.aborted && active < state.maxConcurrency * 2 && queue.length) {
        const item = queue.shift();
        active++;
        processItem(item, signal).finally(() => { active--; scheduleRender(); pump(); });
      }
      if (!queue.length && active === 0) resolve();
    };
    pump();
  });
}

async function start() {
  showError("");
  if (!state.items.length || state.builtVersion !== state.inputVersion || state.items.every((i) => i.status === "done")) buildItems();
  const pending = state.items.filter((i) => i.status === "pending" || i.status === "error");
  if (!pending.length && !state.items.length) { showError("Add images first."); return; }
  try { const h = await health(); state.maxConcurrency = Math.max(1, Math.min(4, h.max_concurrency)); } catch { state.maxConcurrency = 2; }
  state.concurrency = state.maxConcurrency;
  state.running = true;
  state.abort = new AbortController();
  state.startedAt = state.startedAt || performance.now();
  $("#batch-start").hidden = true;
  $("#batch-cancel").hidden = false;
  $("#batch-progress").hidden = false;
  $("#batch-results").hidden = false;
  $("#batch-summary").hidden = false;
  for (const it of pending) { it.status = "pending"; it.error = null; }
  renderProgress(); renderTable(); renderUnpaired();
  await runPool(pending, state.abort.signal);
  state.running = false;
  $("#batch-cancel").hidden = true;
  $("#batch-start").hidden = false;
  $("#batch-start").textContent = state.items.some((i) => i.status !== "done" && i.status !== "no-images") ? "Resume" : "Run again";
  $("#batch-export").hidden = false;
  updateStartButton();
  renderProgress(); renderSummary(); renderTable();
}

function pause() { state.abort?.abort(); setStatus("Pausing after the images in progress…", true); }

// ------------------------------------------------------------------ rendering
function counts() {
  const c = { total: state.items.length, done: 0, ready: 0, review: 0, issues: 0, unreadable: 0, errors: 0, noimages: 0, decided: 0 };
  for (const it of state.items) {
    if (it.status === "done") c.done++;
    if (it.status === "error") c.errors++;
    if (it.status === "no-images") c.noimages++;
    const v = it.result?.verdict;
    if (v === "ready_for_approval") c.ready++; else if (v === "needs_review") c.review++; else if (v === "issues_found") c.issues++; else if (v === "unreadable") c.unreadable++;
    if (state.decisions.get(it.key)?.decision) c.decided++;
  }
  return c;
}

function renderProgress() {
  const c = counts();
  const finished = c.done + c.errors;
  const workable = c.total - c.noimages;
  const pct = workable ? Math.round((100 * finished) / workable) : 0;
  const bar = $("#batch-progress .progress__bar");
  bar.setAttribute("aria-valuenow", String(pct));
  bar.querySelector("span").style.width = `${pct}%`;
  const elapsed = performance.now() - state.startedAt;
  const avgItem = finished ? elapsed / finished : 0;
  const remaining = workable - finished;
  const eta = state.running && finished ? ` · about ${seconds(avgItem * remaining / Math.max(1, state.concurrency))} left` : "";
  $("#batch-progress .progress__text").textContent = `${finished} of ${workable} applications checked (${pct}%)${eta}`;
  setStatus(state.running ? `Reading images, ${state.concurrency} at a time…` : finished ? `Done. ${finished} checked in ${seconds(elapsed)}.` : "", state.running);
  renderSummary();
}

function renderSummary() {
  const c = counts();
  const tile = (num, lbl) => el("div", { class: "summary-tile" }, [el("div", { class: "num", text: String(num) }), el("div", { class: "lbl", text: lbl })]);
  const perImage = state.times.length ? `${seconds(percentile(state.times, 0.5))} median · ${seconds(percentile(state.times, 0.95))} p95` : "—";
  $("#batch-summary").replaceChildren(
    tile(c.ready, "Ready for approval"), tile(c.review, "Need review"), tile(c.issues + c.unreadable, "Issues / unreadable"),
    tile(c.errors, "Errors"), tile(state.unpaired.length, "Images not matched"), tile(`${c.decided}/${c.total}`, "Decided"),
    el("div", { class: "summary-tile" }, [el("div", { class: "num", text: perImage.split(" · ")[0].replace(" median", "") }), el("div", { class: "lbl", text: state.times.length ? `per image, median (p95 ${perImage.split(" · ")[1].replace(" p95", "")})` : "per image" })]),
  );
}

function visibleItems() {
  const dec = (it) => state.decisions.get(it.key)?.decision;
  let items = state.items.filter((it) => {
    const v = it.result?.verdict;
    if (state.filter === "attention") return it.status === "error" || it.status === "no-images" || v === "issues_found" || v === "needs_review" || v === "unreadable";
    if (state.filter === "ready") return v === "ready_for_approval";
    if (state.filter === "undecided") return it.status === "done" && !dec(it);
    return true;
  });
  items = items.sort((a, b) => (SEVERITY[a.result?.verdict] ?? 4) - (SEVERITY[b.result?.verdict] ?? 4) || (a.row ?? 0) - (b.row ?? 0));
  return items;
}

function issueList(item) {
  if (!item.result) return null;
  const probs = item.result.checks.filter((c) => c.status !== "match" && c.status !== "info" && c.status !== "not_checked").map((c) => `${c.label}: ${c.status.replace("_", " ")}`);
  const w = item.result.warning;
  if (w.assessment === "not_required") { /* under 0.5% alcohol: no statement required */ }
  else if (!w.present) probs.push("Warning: missing"); else if (!w.exact) probs.push("Warning: wording not exact"); else if (w.anchor_caps !== "match") probs.push("Warning: heading not all caps");
  return probs.length ? el("ul", { class: "usa-list usa-list--unstyled issues" }, probs.map((p) => el("li", { text: p }))) : el("span", { class: "text-base", text: "All checks match" });
}

function decisionCell(item) {
  const d = state.decisions.get(item.key) || {};
  const btn = (val, label) => el("button", { type: "button", class: `usa-button usa-button--outline${d.decision === val ? " is-on" : ""}`, text: label,
    "aria-pressed": d.decision === val ? "true" : "false",
    onclick: () => { state.decisions.set(item.key, { ...d, decision: d.decision === val ? null : val }); renderTable(); renderSummary(); } });
  const note = el("input", { type: "text", class: "note-input", placeholder: "Note (optional)", value: d.note || "", "aria-label": `Note for ${item.key}` });
  note.addEventListener("change", () => state.decisions.set(item.key, { ...(state.decisions.get(item.key) || {}), note: note.value }));
  return el("div", {}, [el("div", { class: "decision-btns" }, [btn("approve", "Approve"), btn("reject", "Reject"), btn("flag", "Flag")]), note]);
}

function renderTable() {
  const items = visibleItems();
  const pages = Math.max(1, Math.ceil(items.length / PAGE_SIZE));
  state.page = Math.min(state.page, pages - 1);
  const slice = items.slice(state.page * PAGE_SIZE, (state.page + 1) * PAGE_SIZE);
  const rows = [];
  for (const it of slice) {
    const v = it.result?.verdict;
    const statusCell = it.status === "working" ? el("span", { class: "status-line is-busy", text: "Reading" })
      : it.status === "error" ? el("span", { class: "status-tag status-mismatch", text: "Error" }) : it.status === "no-images" ? statusTag("not_checked")
      : it.status === "pending" ? el("span", { class: "text-base", text: "Waiting" })
      : v ? el("span", { class: `status-tag status-${VERDICT_STATUS[v]}`, text: VERDICT_WORD[v] }) : statusTag("info");
    const tr = el("tr", { class: it.status === "error" ? "is-error" : "" }, [
      el("td", {}, statusCell),
      el("td", {}, [el("div", { class: "app-id", text: it.application?.application_id || it.key }),
        el("div", { class: "app-brand", text: it.application ? `${it.application.brand_name} · ${it.application.class_type}` : (it.fields?.largest_text ? `Read: ${it.fields.largest_text}` : "") })]),
      el("td", {}, [el("div", { class: "files", text: it.files.map((f) => f.name).join(", ") || "none" }), el("div", { class: "files", text: it.method }),
        it.missing && it.missing.length ? el("div", { class: "files text-secondary-dark", text: `Listed but not uploaded: ${it.missing.join(", ")}` }) : null]),
      el("td", {}, it.status === "error" ? el("span", { class: "text-secondary-dark", text: it.error }) : it.status === "no-images" ? el("span", { text: "No images matched this row." })
        : it.application ? issueList(it) : (it.fields ? el("ul", { class: "usa-list usa-list--unstyled issues" }, [
          el("li", { text: `Alcohol: ${it.fields.alcohol_percent != null ? it.fields.alcohol_percent + "%" : "not read"}` }),
          el("li", { text: `Net contents: ${it.fields.net_contents_ml.length ? it.fields.net_contents_ml.map((m) => m + " mL").join(", ") : "not read"}` }),
          el("li", { text: `Warning: ${it.fields.warning_present ? "present" : "not found"}` })]) : null)),
      el("td", {}, it.status === "done" && it.application ? decisionCell(it) : null),
      el("td", {}, it.status === "done" ? el("button", { type: "button", class: "usa-button usa-button--unstyled", text: state.expanded === it.key ? "Hide" : "Details",
        "aria-expanded": state.expanded === it.key ? "true" : "false", onclick: () => { state.expanded = state.expanded === it.key ? null : it.key; renderTable(); } }) : null),
    ]);
    rows.push(tr);
    if (state.expanded === it.key && it.status === "done") {
      let panel = state.detailCache.get(it.key);
      if (!panel) {
        panel = el("div", { class: "detail-panel" });
        state.detailCache.set(it.key, panel);
        renderDetail(panel, it);
      }
      rows.push(el("tr", { class: "detail-row" }, el("td", { colspan: "6" }, panel)));
    }
  }
  $("#batch-table").replaceChildren(el("table", { class: "usa-table usa-table--stacked batch-table" }, [
    el("thead", {}, el("tr", {}, ["Result", "Application", "Images", "What to look at", "Your decision", ""].map((h) => el("th", { scope: "col", text: h })))),
    el("tbody", {}, rows.length ? rows : el("tr", {}, el("td", { colspan: "6", text: "Nothing to show for this filter." }))),
  ]));
  $("#pager-text").textContent = `Page ${state.page + 1} of ${pages} · ${items.length} application${items.length === 1 ? "" : "s"}`;
  $("#pager-prev").disabled = state.page === 0;
  $("#pager-next").disabled = state.page >= pages - 1;
}

async function renderDetail(panel, it) {
  if (!it.result) {
    panel.replaceChildren(el("p", { text: "Read without application data. Lines:" }), el("ul", { class: "ocr-lines" }, it.lines.map((l) => el("li", { text: l.text }))));
    return;
  }
  const checklist = el("div"), warning = el("div"), figures = el("div");
  panel.replaceChildren(el("p", { class: "text-bold", text: it.result.summary }), el("div", { class: "grid-row grid-gap-4" }, [
    el("div", { class: "desktop:grid-col-7" }, [checklist, el("h4", { text: "Government warning" }), warning]),
    el("div", { class: "desktop:grid-col-5" }, figures)]));
  const crops = await makeCrops(it.files, it.images, it.result.checks);
  const overlays = renderFigures(figures, it.images, it.files, it.lines);
  const select = (check) => { drawOverlays(overlays, it.result.checks, it.result.warning, check.id); panel.querySelectorAll(".checklist tbody tr").forEach((tr) => tr.classList.toggle("is-active", tr.dataset.check === check.id)); };
  renderChecklist(checklist, it.result.checks, select, crops);
  renderWarning(warning, it.result.warning, select);
  drawOverlays(overlays, it.result.checks, it.result.warning, null);
}

function renderUnpaired() {
  const sec = $("#batch-unpaired");
  sec.hidden = state.unpaired.length === 0;
  const list = $("#unpaired-list");
  list.replaceChildren(...state.unpaired.map((name) => {
    const f = state.images.get(name);
    const url = URL.createObjectURL(f);
    const img = el("img", { src: url, alt: "" });
    img.addEventListener("load", () => URL.revokeObjectURL(url), { once: true });
    const sel = el("select", { class: "usa-select", "aria-label": `Application for ${f.name}` }, [
      el("option", { value: "", text: "Choose an application…" }),
      ...state.items.filter((i) => i.application).map((i) => el("option", { value: i.key, text: `${i.key} · ${i.application.brand_name}` })),
    ]);
    sel.addEventListener("change", async () => {
      const it = state.items.find((i) => i.key === sel.value);
      if (!it) return;
      it.files.push(f); it.method = "assigned by agent"; it.status = "pending"; state.detailCache.delete(it.key);
      state.unpaired = state.unpaired.filter((n) => n !== name);
      renderUnpaired();
      const ac = new AbortController();
      await processItem(it, ac.signal);
      renderTable(); renderSummary();
    });
    return el("li", {}, [img, el("div", {}, [el("div", { class: "file-name", text: f.name })]), sel]);
  }));
}

// ------------------------------------------------------------------ export
function csvCell(v) {
  let s = v == null ? "" : String(v);
  if (/^[=+\-@\t\r]/.test(s)) s = "'" + s; // neutralize spreadsheet formulas
  return `"${s.replace(/"/g, '""')}"`;
}
function exportCsv() {
  const head = ["application_id", "brand_name", "class_type", "verdict", "summary", "brand_status", "class_status", "alcohol_status", "net_contents_status",
    "bottler_status", "origin_status", "warning_present", "warning_exact", "warning_anchor_caps", "decision", "note", "images", "processing_ms", "checked_at"];
  const lines = [head.map(csvCell).join(",")];
  const st = (it, id) => it.result?.checks.find((c) => c.id === id)?.status || "";
  for (const it of state.items) {
    const d = state.decisions.get(it.key) || {};
    const w = it.result?.warning;
    lines.push([it.application?.application_id || it.key, it.application?.brand_name || it.fields?.largest_text || "", it.application?.class_type || "",
      it.result?.verdict || it.status, it.result?.summary || it.error || "", st(it, "brand_name"), st(it, "class_type"), st(it, "alcohol_content"),
      st(it, "net_contents"), st(it, "bottler"), st(it, "country_of_origin"), w ? w.present : "", w ? w.exact : "", w ? w.anchor_caps : "",
      d.decision || "", d.note || "", it.files.map((f) => f.name).join(";"), it.ms, new Date().toISOString()].map(csvCell).join(","));
  }
  const blob = new Blob(["﻿" + lines.join("\r\n")], { type: "text/csv;charset=utf-8" });
  const a = el("a", { href: URL.createObjectURL(blob), download: `label-check-batch-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-")}.csv` });
  document.body.append(a); a.click(); a.remove();
}

// ------------------------------------------------------------------ demo batch
async function loadDemo() {
  setStatus("Loading demo batch…", true);
  const names = ["APP-001_front.png", "APP-001_back.png", "APP-002_front.png", "APP-002_back.png", "APP-003_front.png", "APP-003_back.png",
    "APP-005_front.png", "APP-005_back.png", "APP-007_front.png", "APP-007_back.png"];
  const files = [];
  for (const n of names) { const b = await (await fetch(`/static/samples/batch/${n}`)).blob(); files.push(new File([b], n, { type: "image/png" })); }
  state.images = new Map(); state.items = []; state.extractions = new Map(); state.decisions = new Map(); state.times = []; state.startedAt = 0;
  addImages(files);
  const csvBlob = await (await fetch("/static/samples/batch/applications.csv")).blob();
  await setCsv(new File([csvBlob], "applications.csv", { type: "text/csv" }));
  setStatus("");
  await start();
}

// ------------------------------------------------------------------ boot
function boot() {
  const dz = $("#batch-dropzone");
  if (!dz) return;
  ["dragenter", "dragover"].forEach((t) => dz.addEventListener(t, (e) => { e.preventDefault(); dz.classList.add("is-dragover"); }));
  ["dragleave", "drop"].forEach((t) => dz.addEventListener(t, (e) => { e.preventDefault(); dz.classList.remove("is-dragover"); }));
  dz.addEventListener("drop", (e) => addImages(e.dataTransfer.files));
  $("#batch-files").addEventListener("change", (e) => { addImages(e.target.files); e.target.value = ""; });
  $("#batch-folder").addEventListener("change", (e) => { addImages(e.target.files); e.target.value = ""; });
  $("#batch-csv").addEventListener("change", (e) => { if (e.target.files[0]) setCsv(e.target.files[0]); e.target.value = ""; });
  $("#batch-start").addEventListener("click", start);
  $("#batch-cancel").addEventListener("click", pause);
  $("#batch-export").addEventListener("click", exportCsv);
  $("#batch-demo").addEventListener("click", loadDemo);
  document.querySelectorAll("[data-filter]").forEach((b) => b.addEventListener("click", () => {
    state.filter = b.dataset.filter; state.page = 0;
    document.querySelectorAll("[data-filter]").forEach((x) => x.classList.toggle("is-on", x === b));
    renderTable();
  }));
  $("#pager-prev").addEventListener("click", () => { state.page--; renderTable(); });
  $("#pager-next").addEventListener("click", () => { state.page++; renderTable(); });
  window.addEventListener("beforeunload", (e) => { if (state.items.some((i) => i.status === "done")) { e.preventDefault(); e.returnValue = ""; } });
}

boot();
