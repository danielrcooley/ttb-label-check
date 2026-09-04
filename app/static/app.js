// Controller for the single-application screen. Vanilla ES module, no build step.
import { ApiError, health, verify } from "./api.js";
import { decisionControls, downloadCsv, drawOverlays, el, exportRow, exportStamp, makeCrops, renderChecklist, renderFigures, renderOcrLines, renderVerdict, renderWarning } from "./render.js";

const MAX_IMAGES = 6;
const MAX_BYTES = 10 * 1024 * 1024;
const ACCEPT = /^image\/(png|jpeg|gif|webp|tiff|bmp)$/;

const $ = (sel) => document.querySelector(sel);
const state = { files: [], result: null, overlays: new Map(), activeId: null, samples: null, app: null, decision: null, elapsedMs: 0 };

// ------------------------------------------------------------------ icons (sprite inlined once)
async function loadSprite() {
  try {
    const svg = await (await fetch("/static/uswds/img/sprite.svg")).text();
    const holder = document.createElement("div");
    holder.hidden = true;
    holder.innerHTML = svg; // static, same-origin asset shipped with the app
    document.body.prepend(holder);
  } catch { /* icons degrade to text-only status words */ }
}

// ------------------------------------------------------------------ views
function showView(name) {
  document.querySelectorAll("[data-view-panel]").forEach((p) => { p.hidden = p.dataset.viewPanel !== name; });
  document.querySelectorAll(".usa-nav-link[data-view]").forEach((a) => {
    a.classList.toggle("usa-current", a.dataset.view === name);
    if (a.dataset.view === name) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
  });
}
function routeFromHash() { showView(["check", "batch", "about", "accessibility"].includes(location.hash.slice(1)) ? location.hash.slice(1) : "check"); }

// ------------------------------------------------------------------ display theme
function wireTheme() {
  // theme.js applied the stored choice before the first paint; here the radios reflect it and change it.
  const choice = document.documentElement.dataset.themeChoice || "light";
  document.querySelectorAll("input[name=theme]").forEach((r) => {
    r.checked = r.value === choice;
    r.addEventListener("change", () => { if (window.lcApplyTheme) window.lcApplyTheme(r.value); });
  });
}

// ------------------------------------------------------------------ files
function setStatus(text, busy = false) {
  const s = $("#status");
  s.textContent = text;
  s.classList.toggle("is-busy", busy);
}
function showFormError(msg, hint = "") {
  const box = $("#form-error");
  box.querySelector("p").textContent = hint ? `${msg} ${hint}` : msg;
  box.hidden = !msg;
}
function humanSize(n) { return n > 1024 * 1024 ? `${(n / 1024 / 1024).toFixed(1)} MB` : `${Math.round(n / 1024)} KB`; }

function renderFileList() {
  const list = $("#file-list");
  list.replaceChildren(...state.files.map((f, i) => {
    const url = URL.createObjectURL(f);
    const img = el("img", { src: url, alt: "" });
    img.addEventListener("load", () => URL.revokeObjectURL(url), { once: true });
    return el("li", {}, [
      img,
      el("div", {}, [el("div", { class: "file-name", text: f.name }), el("div", { class: "file-meta", text: `${f.type || "image"} · ${humanSize(f.size)}` })]),
      el("button", { type: "button", class: "usa-button usa-button--unstyled", text: "Remove", "aria-label": `Remove ${f.name}`, onclick: () => { state.files.splice(i, 1); renderFileList(); } }),
    ]);
  }));
  $("#clear-files").hidden = state.files.length === 0;
}

function addFiles(fileList) {
  const problems = [];
  for (const f of fileList) {
    if (state.files.length >= MAX_IMAGES) { problems.push(`Only ${MAX_IMAGES} images per application; "${f.name}" was not added.`); break; }
    if (f.type && !ACCEPT.test(f.type)) { problems.push(`"${f.name}" is not a supported image type (PNG, JPEG, GIF, WebP, TIFF, BMP).`); continue; }
    if (f.size > MAX_BYTES) { problems.push(`"${f.name}" is ${humanSize(f.size)}; the limit is 10 MB per image.`); continue; }
    if (f.size === 0) { problems.push(`"${f.name}" is empty.`); continue; }
    if (state.files.some((g) => g.name === f.name && g.size === f.size)) continue; // same file twice
    state.files.push(f);
  }
  renderFileList();
  showFormError(problems.join(" "));
}

function wireDropzone() {
  const dz = $("#dropzone");
  const input = $("#file-input");
  input.addEventListener("change", () => { addFiles(input.files); input.value = ""; });
  ["dragenter", "dragover"].forEach((t) => dz.addEventListener(t, (e) => { e.preventDefault(); dz.classList.add("is-dragover"); }));
  ["dragleave", "drop"].forEach((t) => dz.addEventListener(t, (e) => { e.preventDefault(); dz.classList.remove("is-dragover"); }));
  dz.addEventListener("drop", (e) => addFiles(e.dataTransfer.files));
  $("#clear-files").addEventListener("click", () => { state.files = []; renderFileList(); });
  document.addEventListener("paste", (e) => {
    const imgs = [...(e.clipboardData?.files || [])].filter((f) => ACCEPT.test(f.type));
    if (imgs.length) addFiles(imgs);
  });
}

// ------------------------------------------------------------------ form
function readApplication() {
  const form = $("#check-form");
  const val = (id) => form.querySelector(`#${id}`).value.trim();
  const app = {
    beverage_type: form.querySelector("input[name=beverage_type]:checked").value,
    brand_name: val("brand_name"),
    class_type: val("class_type"),
    alcohol_content: val("alcohol_content") || null,
    net_contents: val("net_contents") || null,
    bottler: val("bottler") || null,
    country_of_origin: val("country_of_origin") || null,
    imported: form.querySelector("#imported").checked,
    application_id: val("application_id") || null,
  };
  return app;
}

function fillApplication(app) {
  const form = $("#check-form");
  form.querySelector(`input[name=beverage_type][value=${app.beverage_type}]`).checked = true;
  for (const id of ["brand_name", "class_type", "alcohol_content", "net_contents", "bottler", "country_of_origin", "application_id"]) {
    form.querySelector(`#${id}`).value = app[id] || "";
  }
  form.querySelector("#imported").checked = Boolean(app.imported);
  const hasOptional = app.country_of_origin || app.application_id || app.imported;
  const btn = form.querySelector("[aria-controls=optional-fields]");
  if (hasOptional && btn.getAttribute("aria-expanded") !== "true") btn.click();
}

function validate(app) {
  const missing = [];
  if (!state.files.length) missing.push("at least one label image");
  if (!app.brand_name) missing.push("the brand name");
  if (!app.class_type) missing.push("the class / type");
  return missing;
}

// ------------------------------------------------------------------ samples
async function loadSamples() {
  try { state.samples = await (await fetch("/static/samples/samples.json")).json(); } catch { state.samples = []; }
}
async function useSample(id) {
  const s = (state.samples || []).find((x) => x.id === id);
  if (!s) return;
  $("#sample-blurb").textContent = s.blurb;
  fillApplication(s.application);
  setStatus("Loading sample images…", true);
  const files = [];
  for (const name of s.images) {
    const blob = await (await fetch(`/static/samples/${name}`)).blob();
    files.push(new File([blob], name, { type: blob.type || "image/png" }));
  }
  state.files = files;
  renderFileList();
  setStatus("");
  await runCheck();
}

// ------------------------------------------------------------------ check
function selectCheck(check) {
  state.activeId = check.id;
  drawOverlays(state.overlays, state.result.checks, state.result.warning, check.id);
  document.querySelectorAll(".checklist tbody tr").forEach((tr) => tr.classList.toggle("is-active", tr.dataset.check === check.id));
  const ev = check.evidence && check.evidence[0];
  if (ev) {
    const fig = $("#figures").children[ev.image_index];
    fig?.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "nearest" });
  }
}

async function runCheck() {
  const app = readApplication();
  const missing = validate(app);
  if (missing.length) { showFormError(`Please add ${missing.join(", ")}.`); return; }
  showFormError("");
  const btn = $("#check-btn");
  btn.disabled = true;
  setStatus(`Reading ${state.files.length} image${state.files.length === 1 ? "" : "s"}…`, true);
  const t0 = performance.now();
  try {
    const result = await verify(state.files, app);
    state.result = result;
    state.app = app;
    state.decision = null;
    state.activeId = null;
    const crops = await makeCrops(state.files, result.images, result.checks);
    renderVerdict($("#verdict"), result);
    renderChecklist($("#checklist"), result.checks, selectCheck, crops);
    renderWarning($("#warning-report"), result.warning, selectCheck);
    state.overlays = renderFigures($("#figures"), result.images, state.files, result.lines);
    drawOverlays(state.overlays, result.checks, result.warning, null);
    renderOcrLines($("#ocr-lines"), result.lines);
    state.elapsedMs = Math.round(performance.now() - t0);
    renderDecision();
    const results = $("#results");
    results.hidden = false;
    results.focus({ preventScroll: false });
    results.scrollIntoView({ behavior: "smooth", block: "start" });
    setStatus(`Done in ${((performance.now() - t0) / 1000).toFixed(1)} s.`);
  } catch (err) {
    if (err instanceof ApiError) {
      const extra = err.status === 429 ? " The service is busy; try again in a moment." : "";
      showFormError(err.message + extra, err.hint);
    } else {
      showFormError("Could not reach the verification service.", "Check your connection and try again.");
    }
    setStatus("");
  } finally {
    btn.disabled = false;
  }
}

// ------------------------------------------------------------------ decision, export, print
function renderDecision() {
  const box = $("#decision");
  box.replaceChildren(
    el("h3", { class: "margin-top-0", text: "Your decision" }),
    el("p", { class: "usa-hint", text: "Goes into the export and the printout only; nothing is stored on the server." }),
    decisionControls(() => state.decision || {}, (next) => { state.decision = next; renderDecision(); }, "Note for this application"),
    el("div", { class: "decision-actions" }, [
      el("button", { type: "button", class: "usa-button usa-button--outline", text: "Export result (CSV)", onclick: exportSingle }),
      el("button", { type: "button", class: "usa-button usa-button--outline", text: "Print", onclick: () => window.print() }),
    ]),
  );
}

function exportSingle() {
  const app = state.app || readApplication();
  const stem = (app.application_id || app.brand_name || "result").replace(/[^A-Za-z0-9_-]+/g, "_").slice(0, 40);
  downloadCsv(`label-check-${stem}-${exportStamp()}.csv`, [exportRow({
    application: app, result: state.result, status: "done", decision: state.decision, files: state.files, elapsedMs: state.elapsedMs,
  })]);
}

// ------------------------------------------------------------------ boot
async function boot() {
  await loadSprite();
  wireDropzone();
  wireTheme();
  routeFromHash();
  window.addEventListener("hashchange", routeFromHash);
  $("#check-form").addEventListener("submit", (e) => { e.preventDefault(); runCheck(); });
  document.querySelectorAll("[data-sample]").forEach((b) => b.addEventListener("click", () => useSample(b.dataset.sample)));
  window.addEventListener("beforeunload", (e) => { if (state.result) { e.preventDefault(); e.returnValue = ""; } });
  loadSamples();
  try {
    const h = await health();
    $("#build-info").textContent = `Build ${h.git_sha} · engine ${h.engine.name} · ${h.max_concurrency} worker${h.max_concurrency === 1 ? "" : "s"}.`;
    if (!h.ready) setStatus("The text-recognition engine is starting up…", true);
  } catch { /* footer stays generic */ }
}

boot();
