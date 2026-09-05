// API client. Every server error arrives as {code, message, hint, request_id}; we surface message + hint.

export class ApiError extends Error {
  /**
   * @param {number} status
   * @param {{code?: string, message?: string, hint?: string, request_id?: string}} body
   * @param {number|null} retryAfter seconds, when the server asked us to back off
   */
  constructor(status, body, retryAfter = null) {
    super(body.message || `Request failed (${status})`);
    this.status = status;
    this.code = body.code || "error";
    this.hint = body.hint || "";
    this.requestId = body.request_id || "";
    this.retryAfter = retryAfter;
    if (status >= 500 && this.requestId) this.hint = `${this.hint} Request id ${this.requestId}.`.trim(); // the 500 text asks for it
  }
}

async function parse(resp) {
  const text = await resp.text();
  let body = {};
  try { body = text ? JSON.parse(text) : {}; } catch { body = { message: text.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim().slice(0, 200) }; }
  if (body === null || typeof body !== "object" || Array.isArray(body)) body = {}; // "null" or a bare value is not an envelope
  if (!resp.ok) {
    const ra = resp.headers.get("Retry-After");
    if (!body.message && typeof body.detail === "string") body.message = body.detail; // a framework error without our envelope
    throw new ApiError(resp.status, body, ra ? Number(ra) : null);
  }
  return body;
}

/** @returns {Promise<object>} health payload */
export async function health() {
  return parse(await fetch("/api/v1/health", { cache: "no-store" }));
}

/**
 * Verify one application against its images.
 * @param {File[]} files
 * @param {object} application
 * @param {{batch?: boolean, signal?: AbortSignal}} [opts]
 */
export async function verify(files, application, opts = {}) {
  const fd = new FormData();
  fd.append("application", JSON.stringify(application));
  for (const f of files) fd.append("images", f, f.name);
  const headers = opts.batch ? { "X-Batch": "1" } : {};
  return parse(await fetch("/api/v1/verify", { method: "POST", body: fd, headers, signal: opts.signal }));
}

/** Extract-only: read a label without application data (batch mode). */
export async function extract(files, opts = {}) {
  const fd = new FormData();
  for (const f of files) fd.append("images", f, f.name);
  const headers = opts.batch ? { "X-Batch": "1" } : {};
  return parse(await fetch("/api/v1/extract", { method: "POST", body: fd, headers, signal: opts.signal }));
}

/** Compare previously extracted lines with application rows, up to 100 items per call. */
export async function compare(items, opts = {}) {
  return parse(await fetch("/api/v1/compare", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ items }), signal: opts.signal,
  }));
}
