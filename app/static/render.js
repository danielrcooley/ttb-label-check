// Results rendering: verdict, checklist, warning report, label figures with highlight overlays,
// and evidence crops cut from the original image in the browser. All user/OCR text goes through
// textContent; nothing is ever inserted as HTML.

const STATUS = {
  match: { word: "Match", icon: "check_circle" },
  needs_review: { word: "Needs review", icon: "warning" },
  mismatch: { word: "Mismatch", icon: "cancel" },
  not_found: { word: "Not found", icon: "error" },
  not_checked: { word: "Not checked", icon: "remove_circle" },
  info: { word: "Info", icon: "info" },
};

const VERDICT = {
  ready_for_approval: { heading: "Ready for your approval", kind: "success" },
  needs_review: { heading: "Please confirm the items marked", kind: "warning" },
  issues_found: { heading: "Issues found", kind: "error" },
  unreadable: { heading: "Could not read the images", kind: "error" },
};

/** Tiny DOM helper: el("div", {class: "x", text: "hi"}, [children]) */
export function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "text") node.textContent = String(v);
    else if (k === "class") node.className = v;
    else if (k === "dataset") Object.assign(node.dataset, v);
    else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v === true ? "" : String(v));
  }
  for (const c of [].concat(children)) {
    if (c === null || c === undefined) continue;
    node.append(typeof c === "string" ? document.createTextNode(c) : c);
  }
  return node;
}

export function icon(name, cls = "usa-icon") {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("class", cls);
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("focusable", "false");
  svg.setAttribute("role", "img");
  const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
  use.setAttribute("href", `#${name}`);
  svg.append(use);
  return svg;
}

export function statusTag(status) {
  const s = STATUS[status] || STATUS.not_checked;
  return el("span", { class: `status-tag status-${status}` }, [icon(s.icon), s.word]);
}

function seconds(ms) { return `${(ms / 1000).toFixed(1)} s`; }

export function renderVerdict(container, result) {
  const v = VERDICT[result.verdict] || VERDICT.needs_review;
  container.replaceChildren(
    el("div", { class: `usa-alert usa-alert--${v.kind} verdict`, role: "status" }, [
      el("div", { class: "usa-alert__body" }, [
        el("h2", { class: "usa-alert__heading", text: v.heading }),
        el("p", { class: "usa-alert__text", text: result.summary }),
        el("p", { class: "usa-alert__text timing" }, [
          `Checked in ${seconds(result.timing.total_ms)}`,
          el("span", { class: "text-normal" }, ` (target: under 5 seconds). ${result.images.length} image${result.images.length === 1 ? "" : "s"} read.`),
        ]),
      ]),
    ]),
  );
}

/**
 * @param {HTMLElement} container
 * @param {object[]} checks
 * @param {(check: object) => void} onSelect
 * @param {Map<string, string>} crops check id -> data URL
 */
export function renderChecklist(container, checks, onSelect, crops) {
  const rows = checks.map((c) => {
    const tr = el("tr", { dataset: { check: c.id }, tabindex: "-1" }, [
      el("td", {}, statusTag(c.status)),
      el("td", {}, [
        el("div", { class: "check-label", text: c.label }),
        el("div", { class: "check-note", text: c.note }),
        c.rule ? el("div", { class: "rule", text: c.rule }) : null,
      ]),
      el("td", { class: "expected", text: c.expected || "—" }),
      el("td", {}, [
        el("div", { class: "found", text: c.found || (c.status === "not_found" ? "nothing similar found" : "—") }),
        crops.get(c.id) ? el("img", { class: "crop", src: crops.get(c.id), alt: `Label region where "${c.found || ""}" was found` }) : null,
      ]),
    ]);
    tr.addEventListener("click", () => onSelect(c));
    tr.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect(c); } });
    tr.tabIndex = 0;
    return tr;
  });
  container.replaceChildren(
    el("table", { class: "usa-table usa-table--stacked checklist width-full" }, [
      el("thead", {}, el("tr", {}, [
        el("th", { scope: "col", text: "Status" }), el("th", { scope: "col", text: "Check" }),
        el("th", { scope: "col", text: "Application says" }), el("th", { scope: "col", text: "Label says" }),
      ])),
      el("tbody", {}, rows),
    ]),
  );
}

function renderDiff(diff) {
  // "-a b | +c" -> spans
  const wrap = el("span", { class: "diff" });
  for (const part of diff.split(" | ")) {
    if (part.startsWith("-")) wrap.append(el("span", { class: "del", text: part.slice(1) }), " ");
    else if (part.startsWith("+")) wrap.append(el("span", { class: "ins", text: part.slice(1) }), " ");
    else wrap.append(part, " ");
  }
  return wrap;
}

export function renderWarning(container, w, onSelect) {
  const overall = !w.present ? "not_found" : w.assessment === "exact" && w.anchor_caps === "match" ? "match"
    : w.assessment === "wording" ? "mismatch" : "needs_review";
  const card = el("div", { class: "warning-card" }, [
    el("div", { class: "warning-head" }, [
      statusTag(overall),
      el("span", { class: "text-bold", text: !w.present ? "No warning statement found" : w.exact ? "Wording is exact" : "Wording is not exact" }),
      w.present ? el("button", { type: "button", class: "usa-button usa-button--unstyled", text: "Show on label", onclick: () => onSelect({ id: "warning", evidence: w.evidence }) }) : null,
    ]),
    w.present ? el("dl", { class: "margin-top-2" }, [
      el("dt", { class: "text-bold", text: "As read from the label" }),
      el("dd", { class: "margin-left-0 margin-top-05" }, el("div", { class: "found-text", text: w.found_text })),
      w.diff ? el("dt", { class: "text-bold margin-top-2", text: "Differences from the required text" }) : null,
      w.diff ? el("dd", { class: "margin-left-0 margin-top-05" }, renderDiff(w.diff)) : null,
      el("dt", { class: "text-bold margin-top-2", text: "Format checks" }),
      el("dd", { class: "margin-left-0 margin-top-05" }, el("ul", { class: "usa-list usa-list--unstyled" }, [
        el("li", {}, [statusTag(w.anchor_caps), " ", "GOVERNMENT WARNING in capital letters"]),
        el("li", { class: "margin-top-05" }, [statusTag(w.anchor_bold), " ", "GOVERNMENT WARNING in bold type"]),
        el("li", { class: "margin-top-05" }, [statusTag(w.body_not_bold), " ", "Remainder of the statement not in bold"]),
      ])),
    ]) : null,
    el("ul", { class: "usa-list" }, w.notes.map((n) => el("li", { text: n }))),
    el("p", { class: "rule text-base", text: w.rule }),
  ]);
  container.replaceChildren(card);
}

/**
 * Render each image with an SVG overlay in canonical coordinates.
 * @returns {Map<number, SVGSVGElement>} image index -> overlay
 */
export function renderFigures(container, images, files, lines) {
  container.replaceChildren();
  const overlays = new Map();
  images.forEach((im, i) => {
    const url = URL.createObjectURL(files[i]);
    const img = el("img", { src: url, alt: `Label image ${i + 1}${im.filename ? `: ${im.filename}` : ""}` });
    img.addEventListener("load", () => URL.revokeObjectURL(url), { once: true });
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("class", "overlay");
    svg.setAttribute("viewBox", `0 0 ${im.width} ${im.height}`);
    svg.setAttribute("preserveAspectRatio", "none");
    svg.setAttribute("aria-hidden", "true");
    overlays.set(i, svg);
    const readLines = lines.filter((l) => l.image_index === i).length;
    const q = im.quality;
    const caption = [
      im.filename || `Image ${i + 1}`, `${im.width} × ${im.height}`, `${readLines} line${readLines === 1 ? "" : "s"} read`,
      im.rotated_degrees ? `rotated ${im.rotated_degrees}° to read` : null,
      q.readable ? null : `Not readable: ${q.reason || ""}`,
    ].filter(Boolean).join(" · ");
    container.append(el("figure", { class: "label-figure" }, [
      el("div", { class: "label-stage" }, [img, svg]),
      el("figcaption", { text: caption }),
    ]));
  });
  return overlays;
}

function polygonFor(quad, cls) {
  const p = document.createElementNS("http://www.w3.org/2000/svg", "polygon");
  p.setAttribute("points", quad.map(([x, y]) => `${x},${y}`).join(" "));
  if (cls) p.setAttribute("class", cls);
  return p;
}

/** Draw all evidence faintly; the active check's evidence strongly. */
export function drawOverlays(overlays, checks, warning, activeId) {
  for (const svg of overlays.values()) svg.replaceChildren();
  const items = [...checks.map((c) => ({ id: c.id, status: c.status, evidence: c.evidence })),
    { id: "warning", status: warning.exact ? "match" : "needs_review", evidence: warning.evidence || [] }];
  for (const it of items) {
    for (const ev of it.evidence) {
      const svg = overlays.get(ev.image_index);
      if (!svg) continue;
      const bad = it.status === "mismatch" || it.status === "not_found";
      svg.append(polygonFor(ev.box, [it.id === activeId ? "is-active" : "", bad ? "is-bad" : ""].join(" ").trim()));
    }
  }
}

/**
 * Cut evidence crops from the original images. Uses the browser's EXIF-aware decoder so the
 * bitmap is in the same oriented space as the server's coordinates; verifies dimensions match.
 * @returns {Promise<Map<string, string>>} check id -> data URL
 */
export async function makeCrops(files, images, checks) {
  const crops = new Map();
  const bitmaps = new Map();
  for (const c of checks) {
    const ev = c.evidence && c.evidence[0];
    if (!ev) continue;
    const im = images[ev.image_index];
    const file = files[ev.image_index];
    if (!im || !file) continue;
    try {
      if (!bitmaps.has(ev.image_index)) {
        bitmaps.set(ev.image_index, await createImageBitmap(file, { imageOrientation: "from-image" }));
      }
      const bmp = bitmaps.get(ev.image_index);
      if (Math.abs(bmp.width - im.width) > 2 || Math.abs(bmp.height - im.height) > 2) {
        continue; // browser and server disagree on orientation for this file: no crop rather than a wrong one
      }
      const sx = 1, sy = 1;
      const xs = c.evidence.flatMap((e) => e.box.map((p) => p[0]));
      const ys = c.evidence.flatMap((e) => e.box.map((p) => p[1]));
      const pad = 8;
      const x0 = Math.max(0, Math.min(...xs) - pad), y0 = Math.max(0, Math.min(...ys) - pad);
      const x1 = Math.min(im.width, Math.max(...xs) + pad), y1 = Math.min(im.height, Math.max(...ys) + pad);
      const w = Math.max(1, x1 - x0), h = Math.max(1, y1 - y0);
      const scale = Math.min(1, 640 / w, 120 / h);
      const canvas = document.createElement("canvas");
      canvas.width = Math.round(w * scale); canvas.height = Math.round(h * scale);
      canvas.getContext("2d").drawImage(bmp, x0 * sx, y0 * sy, w * sx, h * sy, 0, 0, canvas.width, canvas.height);
      crops.set(c.id, canvas.toDataURL("image/png"));
    } catch { /* crops are a convenience; never fail the result over them */ }
  }
  for (const b of bitmaps.values()) b.close?.();
  return crops;
}

export function renderOcrLines(container, lines) {
  const byImage = new Map();
  for (const l of lines) (byImage.get(l.image_index) || byImage.set(l.image_index, []).get(l.image_index)).push(l);
  container.replaceChildren(...[...byImage.entries()].map(([idx, ls]) =>
    el("div", {}, [
      el("h4", { class: "margin-bottom-05", text: `Image ${idx + 1}` }),
      el("ol", { class: "ocr-lines" }, ls.map((l) => el("li", { text: `${l.text}  (${Math.round(l.confidence * 100)}%)` }))),
    ])));
}
