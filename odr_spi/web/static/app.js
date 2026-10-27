// MPBNL SPI WebFrontend web UI. Plain ES module, no build step.
// All DOM is built with h(), which only ever creates text nodes for content,
// so user-provided strings are never parsed as HTML.

/* ============================== utilities ============================== */

const ICONS = {
  brand: [["path", "M4.9 19.1C1 15.2 1 8.8 4.9 4.9M7.8 16.2c-2.3-2.3-2.3-6.1 0-8.5M16.2 7.8c2.3 2.3 2.3 6.1 0 8.5M19.1 4.9C23 8.8 23 15.1 19.1 19"], ["circle", 12, 12, 2]],
  grid: [["path", "M3 3h7v7H3zM14 3h7v7h-7zM14 14h7v7h-7zM3 14h7v7H3z"]],
  layers: [["path", "M12 2 2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"]],
  activity: [["path", "M22 12h-4l-3 9L9 3l-3 9H2"]],
  import: [["path", "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"]],
  upload: [["path", "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12"]],
  code: [["path", "M16 18l6-6-6-6M8 6l-6 6 6 6"]],
  users: [["path", "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"], ["circle", 9, 7, 4]],
  user: [["path", "M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"], ["circle", 12, 7, 4]],
  sliders: [["path", "M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6"]],
  audit: [["path", "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M16 13H8M16 17H8M10 9H8"]],
  logout: [["path", "M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"]],
  search: [["circle", 11, 11, 8], ["path", "M21 21l-4.35-4.35"]],
  plus: [["path", "M12 5v14M5 12h14"]],
  x: [["path", "M18 6 6 18M6 6l12 12"]],
  check: [["path", "M20 6 9 17l-5-5"]],
  alert: [["path", "M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0zM12 9v4M12 17h.01"]],
  link: [["path", "M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"]],
  image: [["rect", 3, 3, 18, 18, 2], ["circle", 8.5, 8.5, 1.5], ["path", "M21 15l-5-5L5 21"]],
  refresh: [["path", "M23 4v6h-6M1 20v-6h6M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"]],
  trash: [["path", "M3 6h18M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6M10 11v6M14 11v6M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"]],
  folder: [["path", "M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"]],
  folderPlus: [["path", "M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2zM12 11v6M9 14h6"]],
  file: [["path", "M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9zM13 2v7h7"]],
  calendar: [["rect", 3, 4, 18, 18, 2], ["path", "M16 2v4M8 2v4M3 10h18"]],
  chevronsLeft: [["path", "M11 17l-5-5 5-5M18 17l-5-5 5-5"]],
  chevronsRight: [["path", "M13 17l5-5-5-5M6 17l5-5-5-5"]],
  arrowLeft: [["path", "M19 12H5M12 19l-7-7 7-7"]],
  arrowUp: [["path", "M12 19V5M5 12l7-7 7 7"]],
  copy: [["rect", 9, 9, 13, 13, 2], ["path", "M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"]],
  edit: [["path", "M12 20h9M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4z"]],
  zap: [["path", "M13 2 3 14h9l-1 8 10-12h-9l1-8z"]],
  shield: [["path", "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"]],
  globe: [["circle", 12, 12, 10], ["path", "M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"]],
  lock: [["rect", 3, 11, 18, 11, 2], ["path", "M7 11V7a5 5 0 0 1 10 0v4"]],
  info: [["circle", 12, 12, 10], ["path", "M12 16v-4M12 8h.01"]],
  menu: [["path", "M3 12h18M3 6h18M3 18h18"]],
  clock: [["circle", 12, 12, 10], ["path", "M12 6v6l4 2"]],
  radio: [["path", "M4.9 19.1C1 15.2 1 8.8 4.9 4.9M19.1 4.9C23 8.8 23 15.1 19.1 19"], ["circle", 12, 12, 2]],
  sun: [["circle", 12, 12, 4], ["path", "M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"]],
  moon: [["path", "M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"]],
  monitor: [["rect", 2, 3, 20, 14, 2], ["path", "M8 21h8M12 17v4"]],
  heart: [["path", "M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"]],
  login: [["path", "M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4M10 17l5-5-5-5M15 12H3"]],
  braces: [["path", "M8 3H7a2 2 0 0 0-2 2v5a2 2 0 0 1-2 2 2 2 0 0 1 2 2v5c0 1.1.9 2 2 2h1M16 21h1a2 2 0 0 0 2-2v-5c0-1.1.9-2 2-2a2 2 0 0 1-2-2V5a2 2 0 0 0-2-2h-1"]],
  play: [["path", "M5 3l14 9-14 9V3z"]],
  wifiOff: [["path", "M1 1l22 22M16.72 11.06A10.94 10.94 0 0 1 19 12.55M5 12.55a10.94 10.94 0 0 1 5.17-2.39M10.71 5.05A16 16 0 0 1 22.58 9M1.42 9a15.91 15.91 0 0 1 4.7-2.88M8.53 16.11a6 6 0 0 1 6.95 0M12 20h.01"]],
};

const SVGNS = "http://www.w3.org/2000/svg";
function icon(name) {
  const svg = document.createElementNS(SVGNS, "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("fill", "none");
  svg.setAttribute("stroke", "currentColor");
  svg.setAttribute("stroke-width", "2");
  svg.setAttribute("stroke-linecap", "round");
  svg.setAttribute("stroke-linejoin", "round");
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("width", "16");
  svg.setAttribute("height", "16");
  for (const [kind, ...a] of ICONS[name] || []) {
    const el = document.createElementNS(SVGNS, kind);
    if (kind === "path") el.setAttribute("d", a[0]);
    if (kind === "circle") { el.setAttribute("cx", a[0]); el.setAttribute("cy", a[1]); el.setAttribute("r", a[2]); }
    if (kind === "rect") { el.setAttribute("x", a[0]); el.setAttribute("y", a[1]); el.setAttribute("width", a[2]); el.setAttribute("height", a[3]); el.setAttribute("rx", a[4]); }
    svg.appendChild(el);
  }
  return svg;
}

function h(tag, attrs, ...children) {
  const el = document.createElement(tag);
  if (attrs) {
    for (const [k, v] of Object.entries(attrs)) {
      if (v === null || v === undefined || v === false) continue;
      if (k === "class") el.className = v;
      else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
      else if (k === "value") el.value = v;
      else if (k === "checked") el.checked = !!v;
      else if (k === "disabled") el.disabled = !!v;
      else if (k === "selected") el.selected = !!v;
      else if (k === "ref") v(el);
      else el.setAttribute(k, v === true ? "" : v);
    }
  }
  append(el, children);
  return el;
}
function append(el, children) {
  for (const c of children.flat(Infinity)) {
    if (c === null || c === undefined || c === false) continue;
    el.appendChild(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return el;
}
const put = (el, ...children) => append(el, children);
function clear(el) { while (el.firstChild) el.removeChild(el.firstChild); return el; }
function btn(label, opts = {}) {
  return h("button", { class: "btn " + (opts.cls || ""), type: opts.type || "button", onclick: opts.onclick, disabled: opts.disabled, title: opts.title },
    opts.icon ? icon(opts.icon) : null, label);
}
function iconBtn(name, title, onclick) {
  return h("button", { class: "icon-btn", type: "button", title, "aria-label": title, onclick }, icon(name));
}

class ApiError extends Error { constructor(msg, status) { super(msg); this.status = status; } }

async function api(method, url, body, { form = false, quiet = false } = {}) {
  const headers = { "X-Requested-With": "odr-spi" };
  if (S.csrf) headers["X-CSRF-Token"] = S.csrf;
  const opts = { method, headers, credentials: "same-origin" };
  if (body !== undefined) {
    if (form) opts.body = body;
    else { headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(body); }
  }
  let r;
  try { r = await fetch(url, opts); } catch (e) {
    if (!quiet) toast("Cannot reach the server.", "error");
    throw new ApiError("network", 0);
  }
  let data = null;
  try { data = await r.json(); } catch (e) { /* empty */ }
  if (!r.ok) {
    const msg = (data && data.error) || `Request failed (${r.status})`;
    if (r.status === 401 && S.user) { S.user = null; boot(); }
    if (!quiet) toast(msg, "error");
    throw new ApiError(msg, r.status);
  }
  return data;
}

function toast(msg, kind = "") {
  const t = h("div", { class: "toast " + kind, role: kind === "error" ? "alert" : "status" }, msg);
  document.getElementById("toasts").appendChild(t);
  setTimeout(() => t.remove(), kind === "error" ? 7000 : 4000);
}

function fmtAgo(ts) {
  if (!ts) return "never";
  const s = Math.round(Date.now() / 1000 - ts);
  if (s < 0) return "in " + fmtDur(-s);
  if (s < 45) return "just now";
  return fmtDur(s) + " ago";
}
function fmtDur(s) {
  if (s < 90) return `${Math.max(1, Math.round(s))}s`;
  if (s < 5400) return `${Math.round(s / 60)}m`;
  if (s < 129600) return `${Math.round(s / 3600)}h`;
  return `${Math.round(s / 86400)}d`;
}
function fmtIn(ts) {
  if (!ts) return "—";
  const s = Math.round(ts - Date.now() / 1000);
  return s <= 0 ? "now" : "in " + fmtDur(s);
}
function fmtDate(ts) { return ts ? new Date(ts * 1000).toLocaleString() : "—"; }
function fmtBytes(n) {
  if (n == null) return "—";
  if (n < 1024) return n + " B";
  if (n < 1048576) return (n / 1024).toFixed(1) + " KB";
  return (n / 1048576).toFixed(2) + " MB";
}
function initials(name) {
  const w = (name || "?").trim().split(/\s+/).filter(Boolean);
  return ((w[0] || "?")[0] + (w[1] ? w[1][0] : (w[0] || "").slice(1, 2))).toUpperCase();
}
const debounce = (fn, ms) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };

/* ============================== modal helpers ============================== */

function modal({ title, body, foot, wide = false, onclose }) {
  const back = h("div", { class: "modal-back" });
  const close = () => { back.remove(); document.removeEventListener("keydown", esc); onclose && onclose(); };
  const esc = (e) => { if (e.key === "Escape") close(); };
  document.addEventListener("keydown", esc);
  const box = h("div", { class: "modal" + (wide ? " wide" : ""), role: "dialog", "aria-modal": "true" },
    h("div", { class: "modal-head" }, h("h2", null, title), h("span", { class: "spacer" }), iconBtn("x", "Close", close)),
    h("div", { class: "modal-body" }, body),
    foot ? h("div", { class: "modal-foot" }, foot) : null);
  back.addEventListener("mousedown", (e) => { if (e.target === back) close(); });
  back.appendChild(box);
  document.body.appendChild(back);
  const first = box.querySelector("input, select, textarea");
  if (first) setTimeout(() => first.focus(), 30);
  return { close, box };
}

function confirmDialog(text, { okText = "Confirm", danger = false, title = "Are you sure?" } = {}) {
  return new Promise((resolve) => {
    let done = false;
    const m = modal({
      title, body: h("p", null, text),
      foot: [btn("Cancel", { onclick: () => m.close() }),
        btn(okText, { cls: danger ? "danger" : "primary", onclick: () => { done = true; m.close(); resolve(true); } })],
      onclose: () => { if (!done) resolve(false); },
    });
  });
}

function showSecret(title, text, secret) {
  const m = modal({
    title, body: h("div", { class: "stack" }, h("p", null, text), codeBlock(secret)),
    foot: btn("Done", { cls: "primary", onclick: () => m.close() }),
  });
}

function copyText(text) {
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(text).then(() => toast("Copied to clipboard.", "ok"));
  } else {
    const ta = h("textarea", { class: "hidden-copy" });
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand("copy"); toast("Copied to clipboard.", "ok"); } catch (e) { toast("Copy failed - select the text manually.", "error"); }
    ta.remove();
  }
}

function codeBlock(text) {
  return h("div", { class: "code" }, text, h("span", { class: "copy" }, iconBtn("copy", "Copy", () => copyText(text))));
}

// Server-side file browser (admin only). mode: "dir" | "file" | "save"
function fileBrowser({ title = "Choose a location", mode = "dir", exts = "", start = "/", filename = "" } = {}) {
  return new Promise((resolve) => {
    let cur = null, selected = null, done = false;
    const pathBar = h("div", { class: "fs-path" });
    const list = h("div", { class: "fs-list" });
    const info = h("div", { class: "small muted" });
    const nameInput = mode === "save" ? h("input", { type: "text", class: "mono", value: filename || "spi-output.dat" }) : null;
    const chooseBtn = btn(mode === "dir" ? "Use this folder" : mode === "save" ? "Save here" : "Select file", { cls: "primary", onclick: choose });

    async function load(path) {
      let data;
      try { data = await api("GET", `/api/fs?path=${encodeURIComponent(path)}${exts ? "&files=" + encodeURIComponent(exts) : ""}`); }
      catch (e) { if (cur === null && path !== "/") return load("/"); return; }
      cur = data.path; selected = null;
      clear(pathBar);
      const parts = cur.split("/").filter(Boolean);
      pathBar.appendChild(h("button", { onclick: () => load("/") }, "/"));
      parts.forEach((p, i) => {
        pathBar.appendChild(h("button", { onclick: () => load("/" + parts.slice(0, i + 1).join("/")) }, p));
        if (i < parts.length - 1) pathBar.appendChild(h("span", { class: "muted" }, "/"));
      });
      clear(list);
      if (data.parent) list.appendChild(h("div", { class: "fs-item dir", onclick: () => load(data.parent) }, icon("arrowUp"), ".."));
      if (!data.entries.length) list.appendChild(h("div", { class: "fs-item muted" }, "Empty folder"));
      for (const e of data.entries) {
        const full = (cur === "/" ? "" : cur) + "/" + e.name;
        const item = h("div", { class: "fs-item" + (e.dir ? " dir" : "") }, icon(e.dir ? "folder" : "file"),
          h("span", { class: "grow ellipsis" }, e.name), e.dir ? null : h("span", { class: "small muted" }, fmtBytes(e.size)));
        item.addEventListener("click", () => {
          if (e.dir) return load(full);
          list.querySelectorAll(".sel").forEach((x) => x.classList.remove("sel"));
          item.classList.add("sel");
          selected = full;
          if (nameInput) nameInput.value = e.name;
        });
        if (e.dir) item.addEventListener("dblclick", () => load(full));
        list.appendChild(item);
      }
      put(clear(info), data.writable
        ? h("span", { class: "chip green" }, icon("check"), "Writable by the service")
        : h("span", { class: "chip amber" }, icon("lock"), "Not writable by the service user"));
    }
    async function mkdir() {
      const name = prompt("New folder name");
      if (!name) return;
      try { const r = await api("POST", "/api/fs/mkdir", { path: cur, name }); load(r.path); } catch (e) { /* toasted */ }
    }
    function choose() {
      let result = cur;
      if (mode === "file") { if (!selected) return toast("Select a file.", "error"); result = selected; }
      if (mode === "save") {
        const n = nameInput.value.trim();
        if (!n || n.includes("/")) return toast("Enter a file name.", "error");
        result = (cur === "/" ? "" : cur) + "/" + n;
      }
      done = true; m.close(); resolve(result);
    }
    const m = modal({
      title, wide: true,
      body: h("div", { class: "stack" }, pathBar, list, h("div", { class: "row" }, info, h("span", { class: "spacer" }),
        mode !== "file" ? btn("New folder", { cls: "sm ghost", icon: "folderPlus", onclick: mkdir }) : null),
      nameInput ? h("div", { class: "field" }, h("label", null, "File name"), nameInput) : null),
      foot: [btn("Cancel", { onclick: () => m.close() }), chooseBtn],
      onclose: () => { if (!done) resolve(null); },
    });
    const startDir = mode === "save" ? (start || "/").replace(/\/[^/]*$/, "") : start;
    load(startDir || "/");
  });
}

/* ============================== form helpers ============================== */

function field(label, input, { hint, max } = {}) {
  const lbl = h("div", { class: "label-row" }, h("label", null, label));
  if (max && input.tagName !== "SELECT") {
    const count = h("span", { class: "count" });
    const upd = () => { const n = [...(input.value || "")].length; count.textContent = `${n}/${max}`; count.classList.toggle("over", n > max); };
    input.addEventListener("input", upd); upd();
    lbl.appendChild(count);
  }
  return h("div", { class: "field" }, lbl, input, hint ? h("div", { class: "hint" }, hint) : null);
}
const inp = (value, attrs = {}) => h("input", { type: "text", value: value ?? "", ...attrs });
function sel(value, options, attrs = {}) {
  return h("select", attrs, options.map(([v, l]) => h("option", { value: v, selected: String(v) === String(value) }, l)));
}
function toggle(label, checked, attrs = {}) {
  const box = h("input", { type: "checkbox", checked, ...attrs });
  return { el: h("label", { class: "check" }, box, h("span", null, label)), box };
}

/* ============================== app state ============================== */

const S = { user: null, csrf: null, status: null, version: "", muxName: "", collapsed: false, lastBuildId: null, pollTimer: null };

/* ---------- theme (per browser) ---------- */
const THEMES = [["system", "System", "monitor"], ["light", "Light", "sun"], ["dark", "Dark", "moon"]];
function getTheme() {
  try { const t = localStorage.getItem("odrspi.theme"); return t === "light" || t === "dark" ? t : "system"; } catch (e) { return "system"; }
}
function setTheme(t) {
  try { if (t === "system") localStorage.removeItem("odrspi.theme"); else localStorage.setItem("odrspi.theme", t); } catch (e) { /* ignore */ }
  if (t === "system") delete document.documentElement.dataset.theme; else document.documentElement.dataset.theme = t;
}
function themeToggle() {
  const b = h("button", { class: "icon-btn", type: "button" });
  const draw = () => {
    const [, label, ic] = THEMES.find((x) => x[0] === getTheme());
    clear(b).appendChild(icon(ic));
    b.title = `Theme: ${label} (click to change)`;
    b.setAttribute("aria-label", b.title);
  };
  b.addEventListener("click", () => {
    const i = THEMES.findIndex((x) => x[0] === getTheme());
    setTheme(THEMES[(i + 1) % THEMES.length][0]);
    draw();
  });
  draw();
  return b;
}

function setTitle() {
  document.title = S.muxName ? `${S.muxName} · MPBNL SPI WebFrontend` : "MPBNL SPI WebFrontend";
}
try { S.collapsed = localStorage.getItem("odrspi.collapsed") === "1"; } catch (e) { /* ignore */ }

const ROLE_LABEL = { admin: "Administrator", editor: "Editor", station: "Station owner" };
const isEditor = () => S.user && (S.user.role === "admin" || S.user.role === "editor");
const isAdmin = () => S.user && S.user.role === "admin";

const LOGO_SIZES = [
  [32, 32, "Station list icon - shown by almost every receiver"],
  [112, 32, "Rectangle for car and hi-fi displays"],
  [128, 128, "Square, higher resolution"],
  [320, 240, "Widescreen - shown before slideshow loads"],
  [600, 600, "Large square for smart radios and apps"],
];

const GENRES = [
  ["urn:tva:metadata:cs:ContentCS:2002:3.6", "Music"],
  ["urn:tva:metadata:cs:ContentCS:2002:3.6.1", "Classical music"],
  ["urn:tva:metadata:cs:ContentCS:2002:3.6.2", "Jazz"],
  ["urn:tva:metadata:cs:ContentCS:2002:3.6.3", "Background music"],
  ["urn:tva:metadata:cs:ContentCS:2002:3.6.4", "Pop-rock"],
  ["urn:tva:metadata:cs:ContentCS:2002:3.6.5", "Blues / R&B / Soul / Gospel"],
  ["urn:tva:metadata:cs:ContentCS:2002:3.6.6", "Country & Western"],
  ["urn:tva:metadata:cs:ContentCS:2002:3.6.7", "Rap / Hip Hop / Reggae"],
  ["urn:tva:metadata:cs:ContentCS:2002:3.6.8", "Electronic / Club / Urban / Dance"],
  ["urn:tva:metadata:cs:ContentCS:2002:3.6.8.14", "Dance / Dance-pop"],
  ["urn:tva:metadata:cs:ContentCS:2002:3.6.9", "World / Traditional / Folk"],
  ["urn:tva:metadata:cs:ContentCS:2002:3.6.10", "Hit-Chart / Song Requests"],
  ["urn:tva:metadata:cs:ContentCS:2002:3.6.11", "Children's songs"],
  ["urn:tva:metadata:cs:ContentCS:2002:3.1", "Information / Factual"],
  ["urn:tva:metadata:cs:ContentCS:2002:3.1.1", "News"],
  ["urn:tva:metadata:cs:ContentCS:2002:3.2", "Sport"],
  ["urn:tva:metadata:cs:ContentCS:2002:3.4", "Drama / Fiction"],
  ["urn:tva:metadata:cs:ContentCS:2002:3.5", "Entertainment"],
];
const genreLabel = (href) => (GENRES.find((g) => g[0] === href) || [null, href.replace(/^urn:tva:metadata:cs:/, "")])[1];

/* ============================== boot / auth ============================== */

async function boot() {
  stopPolling();
  let st;
  try { st = await api("GET", "/api/state", undefined, { quiet: true }); }
  catch (e) { return renderFatal(); }
  S.version = st.version; S.user = st.user; S.csrf = st.csrf; S.muxName = st.mux_name || "";
  setTitle();
  if (st.setup_required) return renderSetupAccount();
  if (!S.user) return renderLogin();
  if (S.user.must_change_pw) return renderForcedPassword();
  if (!st.setup_complete && isAdmin()) return renderWizard(0);
  renderShell();
}

function renderFatal() {
  const cmds = "sudo systemctl status odr-spi-generator --no-pager\n" +
    "sudo journalctl -u odr-spi-generator -n 50 --no-pager\n" +
    "sudo journalctl -u odr-spi-generator-update -n 50 --no-pager";
  authCard(h("div", { class: "stack" }, h("h1", null, "Cannot reach the server"),
    h("p", { class: "lead" }, "The MPBNL SPI WebFrontend service isn't responding. If an update is installing, give it a minute and retry. Otherwise, check the service on the server:"),
    codeBlock(cmds),
    h("p", { class: "small muted" }, "To start it again: sudo systemctl start odr-spi-generator. The SPI output file keeps broadcasting either way."),
    btn("Retry", { cls: "primary block", icon: "refresh", onclick: boot })), true);
}

function brand() {
  return h("div", { class: "brand" },
    h("img", { class: "brand-logo logo-dark", src: "/static/logo-dark.svg", alt: "MPBNL SPI WebFrontend" }),
    h("img", { class: "brand-logo logo-light", src: "/static/logo-light.svg", alt: "MPBNL SPI WebFrontend" }),
    S.muxName ? h("div", { class: "mux-name", title: "Multiplex" }, icon("radio"), h("span", { class: "ellipsis" }, S.muxName)) : null);
}

function authCard(children, wide = false) {
  const app = clear(document.getElementById("app"));
  const card = h("div", { class: "auth-card" + (wide ? " wide" : "") }, children);
  app.appendChild(h("div", { class: "auth" }, h("div", { class: "auth-wrap" }, brand(), card,
    h("div", { class: "auth-foot" }, `MPBNL © ${new Date().getFullYear()}`))));
  return card;
}

function renderLogin() {
  const u = inp("", { autocomplete: "username", required: true });
  const p = h("input", { type: "password", autocomplete: "current-password", required: true });
  const err = h("div", { class: "banner red hidden" });
  const submit = btn("Sign in", { cls: "primary lg block", type: "submit", icon: "login" });
  const form = h("form", { class: "stack" }, h("h1", null, "Sign in to the panel"),
    h("p", { class: "lead" }, "Manage your stations' logos, EPG and service information."),
    err, field("Username", u), field("Password", p), submit,
    h("p", { class: "auth-help" }, "Forgot your password? Ask an administrator to reset it."));
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    submit.disabled = true;
    try { await api("POST", "/api/login", { username: u.value, password: p.value }, { quiet: true }); boot(); }
    catch (ex) { put(clear(err), icon("alert"), ex.message); err.classList.remove("hidden"); p.value = ""; p.focus(); }
    finally { submit.disabled = false; }
  });
  authCard(form);
  u.focus();
}

function renderSetupAccount() {
  const token = inp(new URLSearchParams(location.search).get("token") || "", { class: "mono", autocomplete: "off" });
  const u = inp("admin", { autocomplete: "username" });
  const dn = inp("");
  const p = h("input", { type: "password", autocomplete: "new-password" });
  const p2 = h("input", { type: "password", autocomplete: "new-password" });
  const submit = btn("Create administrator", { cls: "primary lg", type: "submit" });
  const form = h("form", { class: "stack" },
    h("div", { class: "steps" }, h("i", { class: "on" }), h("i"), h("i"), h("i")),
    h("h1", null, "Welcome"), h("p", { class: "muted" }, "Create the first administrator account. The setup token was printed by the installer - you can show it again with ",
      h("code", null, "sudo odr-spi-generator setup-token"), "."),
    field("Setup token", token), h("div", { class: "grid-2" }, field("Username", u), field("Display name", dn)),
    h("div", { class: "grid-2" }, field("Password", p, { hint: "At least 10 characters." }), field("Confirm password", p2)), submit);
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (p.value !== p2.value) return toast("Passwords do not match.", "error");
    submit.disabled = true;
    try {
      await api("POST", "/api/setup", { token: token.value, username: u.value, display_name: dn.value, password: p.value });
      history.replaceState(null, "", location.pathname);
      boot();
    } catch (ex) { submit.disabled = false; }
  });
  authCard(form, true);
}

function renderForcedPassword() {
  const cur = h("input", { type: "password", autocomplete: "current-password" });
  const p = h("input", { type: "password", autocomplete: "new-password" });
  const p2 = h("input", { type: "password", autocomplete: "new-password" });
  const form = h("form", { class: "stack" }, h("h1", null, "Choose a new password"),
    h("p", { class: "muted" }, "Your password was set by an administrator. Choose your own before continuing."),
    field("Current (temporary) password", cur), field("New password", p, { hint: "At least 10 characters." }), field("Confirm", p2),
    h("div", { class: "row" }, btn("Sign out", { cls: "ghost", onclick: logout }), h("span", { class: "spacer" }), btn("Save password", { cls: "primary", type: "submit" })));
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (p.value !== p2.value) return toast("Passwords do not match.", "error");
    try { await api("POST", "/api/account/password", { current: cur.value, new: p.value }); toast("Password changed.", "ok"); boot(); } catch (ex) { /* toasted */ }
  });
  authCard(form);
}

async function logout() {
  try { await api("POST", "/api/logout", {}); } catch (e) { /* ignore */ }
  S.user = null; S.csrf = null;
  location.hash = "";
  boot();
}

/* ============================== first-run wizard ============================== */

async function renderWizard(step) {
  const steps = h("div", { class: "steps" }, [0, 1, 2, 3].map((i) => h("i", { class: i <= step + 1 ? "on" : "" })));
  if (step === 0) {
    const { ensemble } = await api("GET", "/api/ensemble");
    const ecc = inp(ensemble.ecc, { class: "mono", placeholder: "e1", maxlength: 2 });
    const eid = inp(ensemble.eid, { class: "mono", placeholder: "c185", maxlength: 4 });
    const ln = inp(ensemble.medium_name, { maxlength: 16 });
    const sn = inp(ensemble.short_name, { maxlength: 8 });
    const importBtn = btn("Read from odr-dabmux config…", { cls: "sm", icon: "import", onclick: async () => {
      const path = await fileBrowser({ title: "Select your odr-dabmux configuration", mode: "file", exts: "info,conf,ini,cfg,mux", start: "/home" });
      if (!path) return;
      const fd = new FormData(); fd.append("path", path);
      try {
        const r = await api("POST", "/api/import/dabmux", fd, { form: true });
        ecc.value = r.ensemble.ecc; eid.value = r.ensemble.eid; ln.value = r.ensemble.medium_name || ln.value; sn.value = r.ensemble.short_name || sn.value;
        S.pendingDabmux = r;
        toast(`Found ensemble ${r.ensemble.ecc}.${r.ensemble.eid} with ${r.services.length} audio services - they can be imported at the end.`, "ok");
      } catch (e) { /* toasted */ }
    } });
    const form = h("form", { class: "stack" }, steps, h("h1", null, "Your ensemble"),
      h("p", { class: "muted" }, "These identify your multiplex in the SPI data. They must match your odr-dabmux configuration."),
      h("div", { class: "row" }, importBtn),
      h("div", { class: "grid-2" }, field("ECC (Extended Country Code)", ecc, { hint: "2 hex digits - e.g. e3 for Ireland, e1 for the UK, e1/e2 for Germany" }),
        field("EId (Ensemble ID)", eid, { hint: "4 hex digits" })),
      h("div", { class: "grid-2" }, field("Ensemble label", ln, { max: 16 }), field("Short label", sn, { max: 8 })),
      h("div", { class: "row" }, h("span", { class: "spacer" }), btn("Continue", { cls: "primary", type: "submit" })));
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      try { await api("PUT", "/api/ensemble", { ecc: ecc.value, eid: eid.value, medium_name: ln.value, short_name: sn.value }); renderWizard(1); } catch (ex) { /* toasted */ }
    });
    authCard(form, true);
  } else if (step === 1) {
    const s = await api("GET", "/api/settings");
    const path = inp(s.output_path, { class: "mono", placeholder: "/home/odr/ODR-mmbTools/config/mot/spi-output.dat" });
    const bitrate = bitrateSelect(s.bitrate);
    const addr = h("input", { type: "number", min: 1, max: 1023, value: s.packet_address });
    const form = h("form", { class: "stack" }, steps, h("h1", null, "Output & carousel"),
      h("p", { class: "muted" }, "Where the SPI stream file is written. odr-dabmux reads this file (inputuri) - the service user needs write access to the folder."),
      field("Output file", h("div", { class: "row" }, path, btn("Browse…", { icon: "folder", onclick: async () => {
        const p = await fileBrowser({ title: "Choose where to write the SPI stream", mode: "save", exts: "dat", start: path.value || "/home", filename: (path.value.split("/").pop()) || "spi-output.dat" });
        if (p) path.value = p;
      } }))),
      h("div", { class: "grid-2" }, field("SPI subchannel bitrate", bitrate, { hint: "Must match the bitrate of the SPI subchannel in odr-dabmux." }),
        field("Packet address", addr, { hint: "Matches 'address' in the odr-dabmux component (1 = 0x1)." })),
      h("div", { class: "row" }, btn("Back", { cls: "ghost", onclick: () => renderWizard(0) }), h("span", { class: "spacer" }), btn("Continue", { cls: "primary", type: "submit" })));
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      try { await api("PUT", "/api/settings", { output_path: path.value, bitrate: +bitrate.value, packet_address: +addr.value }); renderWizard(2); } catch (ex) { /* toasted */ }
    });
    authCard(form, true);
  } else if (step === 2) {
    const sn = await api("GET", "/api/mux-snippet");
    const card = authCard(h("div", { class: "stack" }, steps, h("h1", null, "Add SPI to your multiplex"),
      h("p", { class: "muted" }, "Add these blocks to the matching sections of your odr-dabmux configuration and restart the multiplexer. You can adjust ids and protection later under Mux config."),
      sn.warnings.map((w) => h("div", { class: "banner amber" }, icon("alert"), w)),
      snippetBlocks(sn),
      h("div", { class: "row" }, btn("Back", { cls: "ghost", onclick: () => renderWizard(1) }), h("span", { class: "spacer" }), btn("Continue", { cls: "primary", onclick: () => renderWizard(3) }))), true);
    card.classList.add("wide");
  } else {
    const finish = async (hash) => {
      await api("PUT", "/api/settings", { setup_complete: true });
      location.hash = hash; renderShell();
    };
    const dm = S.pendingDabmux;
    authCard(h("div", { class: "stack" }, steps, h("h1", null, "You're set up"),
      h("p", { class: "muted" }, "Next, add your stations. You can import an existing SPI/XSI XML file (logos included), pull the services from your odr-dabmux config, or add stations by hand."),
      h("div", { class: "grid-3" },
        btn("Import SPI XML", { cls: "lg", icon: "import", onclick: () => finish("#/import") }),
        dm ? btn(`Import ${dm.services.length} mux services`, { cls: "lg", icon: "radio", onclick: async () => {
          try { const r = await api("POST", `/api/import/${dm.id}/commit`, { mode: "merge" }); toast(`Imported ${r.created} stations.`, "ok"); } catch (e) { /* expired */ }
          finish("#/stations");
        } }) : null,
        btn("Add stations manually", { cls: "lg", icon: "plus", onclick: () => finish("#/stations") })),
      h("div", { class: "row" }, btn("Back", { cls: "ghost", onclick: () => renderWizard(2) }), h("span", { class: "spacer" }), btn("Go to dashboard", { cls: "primary", onclick: () => finish("#/stations") }))), true);
  }
}

/* ============================== shell ============================== */

const NAV = [
  ["MONITOR", [
    ["stations", "Stations", "grid", () => true],
    ["ensemble", "Ensemble", "layers", () => true],
    ["activity", "Activity", "activity", () => true],
  ]],
  ["MANAGE", [
    ["import", "Import", "import", isEditor],
    ["templates", "EPG templates", "braces", isEditor],
    ["mux", "Mux config", "code", isEditor],
    ["users", "Users", "users", isAdmin],
    ["settings", "Settings", "sliders", isAdmin],
    ["audit", "Audit log", "audit", isAdmin],
  ]],
];

let shellEls = null;

function renderShell() {
  const app = clear(document.getElementById("app"));
  const nav = h("nav", { class: "nav", "aria-label": "Main" });
  for (const [section, items] of NAV) {
    const visible = items.filter((i) => i[3]());
    if (!visible.length) continue;
    nav.appendChild(h("div", { class: "nav-section" }, section));
    for (const [key, label, ic] of visible) {
      nav.appendChild(h("a", { href: "#/" + key, "data-key": key }, icon(ic), h("span", null, label)));
    }
  }
  const monitor = h("div", { class: "monitor" });
  const shell = h("div", { class: "shell" + (S.collapsed ? " collapsed" : "") });
  const side = h("aside", { class: "side" }, brand(), nav,
    h("div", { class: "side-foot" }, monitor,
      h("div", { class: "user-card" },
        h("a", { class: "avatar", href: "#/account", title: "Account" }, initials(S.user.display_name || S.user.username)),
        h("div", { class: "who" }, h("b", { class: "ellipsis" }, S.user.display_name || S.user.username), h("span", null, ROLE_LABEL[S.user.role])),
        themeToggle(), iconBtn("logout", "Sign out", logout)),
      h("button", { class: "collapse-btn", onclick: () => {
        S.collapsed = !S.collapsed; shell.classList.toggle("collapsed", S.collapsed);
        try { localStorage.setItem("odrspi.collapsed", S.collapsed ? "1" : "0"); } catch (e) { /* ignore */ }
      } }, icon("chevronsLeft"), h("span", null, "Collapse"))));
  const crumbs = h("div", { class: "crumbs" });
  const pending = h("div", { class: "row" });
  const content = h("div", { class: "content" });
  const main = h("main", { class: "main" },
    h("div", { class: "topbar" }, h("span", { class: "mobile-only" }, iconBtn("menu", "Menu", () => shell.classList.toggle("mobile-nav"))), crumbs, h("span", { class: "spacer" }), pending),
    content);
  put(shell, side, main);
  app.appendChild(shell);
  shellEls = { nav, monitor, crumbs, pending, content, shell };
  side.addEventListener("click", (e) => { if (e.target.closest("a")) shell.classList.remove("mobile-nav"); });
  window.onhashchange = route;
  route();
  refreshStatus();
}

function setCrumbs(...parts) {
  const c = clear(shellEls.crumbs);
  parts.forEach((p, i) => {
    if (i) c.appendChild(h("span", null, "/"));
    c.appendChild(i === parts.length - 1 ? h("b", null, p.label || p) : h("a", { href: p.href }, p.label));
  });
}

function route() {
  if (!shellEls) return;
  const parts = (location.hash.replace(/^#\/?/, "") || "stations").split("/");
  const key = parts[0];
  shellEls.nav.querySelectorAll("a").forEach((a) => a.classList.toggle("active", a.dataset.key === key));
  const content = clear(shellEls.content);
  const pages = { stations: pageStations, ensemble: pageEnsemble, activity: pageActivity, import: pageImport, mux: pageMux, templates: pageTemplates,
    users: pageUsers, settings: pageSettings, audit: pageAudit, account: pageAccount };
  const fn = pages[key] || pageStations;
  Promise.resolve(fn(content, parts.slice(1))).catch((e) => {
    if (!(e instanceof ApiError)) { console.error(e); toast("Something went wrong rendering this page.", "error"); }
  });
  shellEls.content.parentElement.scrollTop = 0;
}

/* ---------- status polling & apply ---------- */

function stopPolling() { if (S.pollTimer) clearTimeout(S.pollTimer); S.pollTimer = null; }

async function refreshStatus() {
  stopPolling();
  if (!S.user || !shellEls) return;
  try {
    const st = await api("GET", "/api/status", undefined, { quiet: true });
    const prev = S.status;
    S.status = st;
    if (prev && prev.running && !st.running && st.build) {
      const b = st.build;
      if (b.status === "error") toast("Build failed: " + b.message, "error");
      else toast((b.status === "warning" ? "Published with warnings: " : "Published: ") + b.message, b.status === "warning" ? "" : "ok");
      if ((location.hash || "").startsWith("#/activity")) route();
    }
    renderStatus();
  } catch (e) { /* offline - retry */ }
  S.pollTimer = setTimeout(refreshStatus, S.status && S.status.running ? 1500 : 10000);
}

function renderStatus() {
  const st = S.status;
  if (!st || !shellEls) return;
  const b = st.build;
  let dot = "dot", text;
  if (st.running) { dot = "dot amber pulse"; text = "Building carousel…"; }
  else if (!b) { dot = "dot"; text = "Not published yet"; }
  else if (b.status === "error") { dot = "dot red"; text = "Last build failed · " + fmtAgo(b.finished_at); }
  else { dot = b.status === "warning" ? "dot amber" : "dot green"; text = "Carousel live · " + fmtAgo(b.finished_at); }
  put(clear(shellEls.monitor), h("i", { class: dot }), h("span", { class: "ellipsis" }, text));

  const p = clear(shellEls.pending);
  if (st.running) {
    p.appendChild(h("div", { class: "pending" }, h("span", { class: "spin" }), "Publishing…"));
  } else if (st.dirty_since || !st.published) {
    const label = st.published ? "Unpublished changes" : "Not published yet";
    p.appendChild(h("div", { class: "pending" }, icon("alert"), h("span", null, label),
      st.can_apply ? btn("Apply", { cls: "primary sm", icon: "zap", onclick: applyChanges }) : h("span", { class: "small" }, "· an editor must apply")));
  } else if (b && b.status !== "error") {
    p.appendChild(h("div", { class: "pending ok" }, icon("check"), "All changes live"));
  }
}

async function applyChanges() {
  try {
    await api("POST", "/api/apply", {});
    toast("Fetching logo URLs and building the carousel…");
    S.status.running = true;
    renderStatus();
    setTimeout(refreshStatus, 800);
  } catch (e) { /* toasted */ }
}

/* ============================== stations ============================== */

let stationFilter = { q: "", tab: "all" };

function bestLogo(logos) {
  const pref = [[128, 128], [600, 600], [32, 32], [320, 240], [112, 32]];
  for (const [w, hh] of pref) {
    const l = logos.find((x) => x.width === w && x.height === hh && x.file);
    if (l) return l;
  }
  return logos.find((x) => x.file);
}

function logoTile(name, logos, lg = false) {
  const l = bestLogo(logos || []);
  return h("div", { class: "logo-tile" + (lg ? " lg" : "") }, l ? h("img", { src: "/media/" + l.file, alt: "" }) : initials(name));
}

function stationProblems(s) {
  const p = [];
  if (!s.bearers.length) p.push("No SId");
  if (!s.logos.some((l) => l.width === 32 && l.height === 32 && l.file)) p.push("No 32×32 logo");
  if (s.logos.some((l) => l.fetch_status === "error")) p.push("Logo URL failing");
  if (s.epg_feed_status && s.epg_feed_status.startsWith("error")) p.push("EPG feed failing");
  return p;
}

function pageStations(root, parts) {
  if (parts && parts[0]) return pageStationDetail(root, parseInt(parts[0], 10), parts[1]);
  return pageStationList(root);
}

async function pageStationList(root) {
  setCrumbs("Stations");
  const services = await api("GET", "/api/services");
  const grid = h("div", { class: "station-grid" });
  const search = h("input", { type: "search", placeholder: "Search stations or SIds", value: stationFilter.q, "aria-label": "Search" });
  const seg = h("div", { class: "segmented" });
  const tabs = [["all", "All"], ["issues", "Issues"], ["epg", "EPG"], ["off", "Disabled"]];
  const drawSeg = () => {
    clear(seg);
    for (const [k, l] of tabs) seg.appendChild(h("button", { class: stationFilter.tab === k ? "on" : "", onclick: () => { stationFilter.tab = k; drawSeg(); draw(); } }, l));
  };
  const draw = () => {
    clear(grid);
    const q = stationFilter.q.toLowerCase();
    const list = services.filter((s) => {
      if (q && ![s.medium_name, s.short_name, s.long_name, ...s.bearers.map((b) => b.sid)].some((x) => (x || "").toLowerCase().includes(q))) return false;
      if (stationFilter.tab === "issues") return stationProblems(s).length > 0;
      if (stationFilter.tab === "epg") return s.epg_enabled;
      if (stationFilter.tab === "off") return !s.enabled;
      return true;
    });
    if (!services.length) {
      grid.appendChild(h("div", { class: "empty span-all" }, h("h3", null, isEditor() ? "No stations yet" : "No stations assigned to you"),
        h("p", null, isEditor() ? "Import an existing SPI XML file or your odr-dabmux config, or add a station by hand." : "Ask an administrator to give you access to your station."),
        isEditor() ? h("div", { class: "row", }, h("span", { class: "spacer" }), btn("Import", { icon: "import", onclick: () => { location.hash = "#/import"; } }),
          btn("Add station", { cls: "primary", icon: "plus", onclick: addStation }), h("span", { class: "spacer" })) : null));
      return;
    }
    if (!list.length) grid.appendChild(h("div", { class: "empty span-all" }, "No stations match."));
    for (const s of list) grid.appendChild(stationCard(s));
  };
  search.addEventListener("input", debounce(() => { stationFilter.q = search.value; draw(); }, 120));
  drawSeg();
  put(root, 
    h("div", { class: "page-head" }, h("div", null, h("h1", null, "Stations"), h("p", null, `${services.length} station${services.length === 1 ? "" : "s"} in the SPI carousel`)),
      h("span", { class: "spacer" }), isEditor() ? btn("Add station", { cls: "primary", icon: "plus", onclick: addStation }) : null),
    h("div", { class: "row wrap" }, h("div", { class: "search" }, icon("search"), search), seg),
    h("div", { class: "section-gap" }), grid);
  draw();
}

function stationCard(s) {
  const problems = stationProblems(s);
  const sids = s.bearers.map((b) => b.sid.toUpperCase() + (b.scids ? "." + b.scids : ""));
  let pill;
  if (!s.enabled) pill = h("span", { class: "pill muted" }, "Disabled");
  else if (!s.bearers.length) pill = h("span", { class: "pill red" }, icon("wifiOff"), "No SId");
  else pill = h("span", { class: "pill green" }, h("i", { class: "dot green" }), "In carousel");
  const strip = h("div", { class: "logo-strip" }, LOGO_SIZES.map(([w, hh]) => {
    const l = s.logos.find((x) => x.width === w && x.height === hh);
    const scale = 26 / Math.max(w, hh);
    const box = h("div", { class: "box" + (l && l.file ? " has" : "") + (l && l.fetch_status === "error" ? " err" : "") }, l && l.file ? h("img", { src: "/media/" + l.file, alt: "", loading: "lazy" }) : null);
    box.style.width = Math.max(10, Math.round(w * scale)) + "px";
    box.style.height = Math.max(10, Math.round(hh * scale)) + "px";
    return h("div", { class: "logo-slot-mini", title: `${w}×${hh}` + (l ? (l.source === "url" ? " (URL)" : " (uploaded)") : " (missing)") }, box, `${w}×${hh}`);
  }));
  const have = LOGO_SIZES.filter(([w, hh]) => s.logos.some((x) => x.width === w && x.height === hh && x.file)).length;
  const meter = h("div", { class: "meter" }, LOGO_SIZES.map(([w, hh]) => {
    const l = s.logos.find((x) => x.width === w && x.height === hh);
    return h("i", { class: l && l.file ? (l.fetch_status === "error" ? "warn" : "on") : "" });
  }));
  const card = h("button", { class: "station-card" + (problems.length && s.enabled ? " problem" : "") + (s.enabled ? "" : " off"), type: "button",
    onclick: () => { location.hash = `#/stations/${s.id}`; } },
    h("div", { class: "sc-head" }, logoTile(s.medium_name, s.logos),
      h("div", { class: "titles" }, h("h3", { class: "ellipsis" }, s.medium_name || "(unnamed)"),
        h("div", { class: "sub ellipsis" }, s.short_description || s.short_name || "—")), pill),
    h("div", { class: "sc-inset" }, strip),
    h("div", { class: "stack tight" }, h("div", { class: "row" }, h("div", { class: "stat-line" }, h("b", null, have), `of ${LOGO_SIZES.length} logo sizes`),
      h("span", { class: "spacer" }), h("span", { class: "small muted" }, s.epg_enabled ? `EPG · ${s.programme_count} entries${s.epg_feed_url ? " + feed" : ""}` : "EPG off")), meter),
    h("div", { class: "sc-foot" },
      sids.length ? sids.slice(0, 3).map((x) => h("span", { class: "chip mono" }, "SId " + x)) : null,
      problems.filter((p) => p !== "No SId").map((p) => h("span", { class: "chip red" }, icon("alert"), p)),
      s.logos.some((l) => l.source === "url") ? h("span", { class: "chip blue" }, icon("link"), "URL") : null,
      h("span", { class: "when" }, "Updated " + fmtAgo(s.updated_at))));
  return card;
}

function addStation() {
  const ln = inp("", { maxlength: 16 }), sn = inp("", { maxlength: 8 }), sid = inp("", { class: "mono", placeholder: "c586", maxlength: 4 });
  const m = modal({
    title: "Add station",
    body: h("div", { class: "stack" }, field("Name (medium name)", ln, { max: 16 }), field("Short name", sn, { max: 8, hint: "Shown on small displays." }),
      field("Service ID (SId)", sid, { hint: "4 hex digits, as in your odr-dabmux services section. ECC/EId default to the ensemble's." })),
    foot: [btn("Cancel", { onclick: () => m.close() }), btn("Create", { cls: "primary", onclick: async () => {
      try {
        const r = await api("POST", "/api/services", { medium_name: ln.value, short_name: sn.value || ln.value.slice(0, 8),
          bearers: sid.value.trim() ? [{ sid: sid.value.trim(), ecc: "", eid: "", scids: 0 }] : [] });
        m.close(); refreshStatus(); location.hash = `#/stations/${r.id}`;
      } catch (e) { /* toasted */ }
    } })],
  });
}

/* ---------- station detail ---------- */

async function pageStationDetail(root, id, tab) {
  const s = await api("GET", `/api/services/${id}`);
  setCrumbs({ href: "#/stations", label: "Stations" }, s.medium_name || "Station");
  const tabsDef = [["overview", "Overview", "edit"], ["logos", "Logos", "image"], ["epg", "EPG", "calendar"]];
  tab = tabsDef.some((t) => t[0] === tab) ? tab : "overview";
  const body = h("div");
  const tabs = h("div", { class: "tabs", role: "tablist" }, tabsDef.map(([k, l, ic]) =>
    h("button", { class: k === tab ? "on" : "", role: "tab", onclick: () => { location.hash = `#/stations/${id}/${k}`; } }, icon(ic), l)));
  put(root, 
    h("div", { class: "page-head" }, iconBtn("arrowLeft", "Back to stations", () => { location.hash = "#/stations"; }), logoTile(s.medium_name, s.logos, true),
      h("div", { class: "grow" }, h("h1", null, s.medium_name || "(unnamed)"),
        h("p", null, [s.short_name, s.bearers.map((b) => `SId ${b.sid.toUpperCase()}`).join(" · ")].filter(Boolean).join(" · ") || "No service ID")),
      s.enabled ? h("span", { class: "pill green" }, "Enabled") : h("span", { class: "pill muted" }, "Disabled")),
    tabs, body);
  if (tab === "overview") stationOverview(body, s);
  if (tab === "logos") logoManager(body, s.id, s.logos, () => route());
  if (tab === "epg") stationEpg(body, s);
}

function genrePicker(initial, disabled) {
  let values = [...initial];
  const list = h("div", { class: "tag-list" });
  const select = sel("", [["", "Add a genre…"], ...GENRES.map(([v, l]) => [v, `${l}  (${v.split(":").pop()})`]), ["custom", "Custom TV-Anytime URN…"]], { disabled });
  const draw = () => {
    clear(list);
    if (!values.length) list.appendChild(h("span", { class: "muted small" }, "No genres"));
    values.forEach((v) => list.appendChild(h("span", { class: "tag", title: v }, genreLabel(v),
      disabled ? null : h("button", { type: "button", "aria-label": "Remove", onclick: () => { values = values.filter((x) => x !== v); draw(); } }, icon("x")))));
  };
  select.addEventListener("change", () => {
    let v = select.value;
    if (v === "custom") v = (prompt("TV-Anytime genre URN, e.g. urn:tva:metadata:cs:ContentCS:2002:3.6.8") || "").trim();
    if (v && !values.includes(v) && values.length < 10) values.push(v);
    select.value = ""; draw();
  });
  draw();
  return { el: h("div", { class: "stack tight" }, list, disabled ? null : select), get: () => values };
}

function bearerEditor(initial, disabled) {
  const rows = [];
  const wrap = h("div", { class: "stack tight" });
  const table = h("div", { class: "stack tight" });
  const add = (b = { ecc: "", eid: "", sid: "", scids: 0 }) => {
    const r = {
      ecc: inp(b.ecc, { class: "mono", placeholder: "ens", maxlength: 2, disabled, "aria-label": "ECC" }),
      eid: inp(b.eid, { class: "mono", placeholder: "ens", maxlength: 4, disabled, "aria-label": "EId" }),
      sid: inp(b.sid, { class: "mono", placeholder: "c586", maxlength: 4, disabled, "aria-label": "SId" }),
      scids: h("input", { type: "number", min: 0, max: 15, value: b.scids || 0, disabled, "aria-label": "SCIdS" }),
    };
    r.el = h("div", { class: "grid-4" }, r.ecc, r.eid, r.sid, h("div", { class: "row" }, r.scids,
      disabled ? null : iconBtn("trash", "Remove bearer", () => { rows.splice(rows.indexOf(r), 1); r.el.remove(); })));
    rows.push(r); table.appendChild(r.el);
  };
  initial.forEach(add);
  if (!initial.length && !disabled) add();
  put(wrap, h("div", { class: "grid-4 small muted" }, h("span", null, "ECC"), h("span", null, "EId"), h("span", null, "SId"), h("span", null, "SCIdS")), table,
    disabled ? null : h("div", null, btn("Add bearer", { cls: "sm ghost", icon: "plus", onclick: () => add() })));
  return { el: wrap, get: () => rows.map((r) => ({ ecc: r.ecc.value.trim(), eid: r.eid.value.trim(), sid: r.sid.value.trim(), scids: +r.scids.value || 0 })).filter((b) => b.sid) };
}

function stationOverview(root, s) {
  const core = s.can_edit_core;
  const f = {
    medium_name: inp(s.medium_name, { disabled: !core }), short_name: inp(s.short_name, { disabled: !core }),
    long_name: inp(s.long_name, { disabled: !core }),
    short_description: h("textarea", { rows: 2 }, s.short_description),
    long_description: h("textarea", { rows: 5 }, s.long_description),
    website: inp(s.website, { type: "url", placeholder: "https://" }),
  };
  const genres = genrePicker(s.genres, false);
  const bearers = bearerEditor(s.bearers, !core);
  const enabled = toggle("Include this station in the SPI carousel", s.enabled, { disabled: !core });
  const save = async () => {
    const body = { short_description: f.short_description.value, long_description: f.long_description.value, website: f.website.value, genres: genres.get() };
    if (core) Object.assign(body, { medium_name: f.medium_name.value, short_name: f.short_name.value, long_name: f.long_name.value, bearers: bearers.get(), enabled: enabled.box.checked });
    try { await api("PATCH", `/api/services/${s.id}`, body); toast("Saved - click Apply to publish.", "ok"); refreshStatus(); route(); } catch (e) { /* toasted */ }
  };
  put(root, 
    h("div", { class: "grid-2" },
      h("div", { class: "card" }, h("div", { class: "card-head" }, h("div", null, h("h2", null, "Names"), h("p", null, core ? "Shown on receivers in place of the DAB label." : "Names are managed by your multiplex operator."))),
        h("div", { class: "card-body stack" }, field("Name (medium)", f.medium_name, { max: 16 }), field("Short name", f.short_name, { max: 8 }), field("Long name", f.long_name, { max: 128, hint: "Optional, for receivers with large displays." }))),
      h("div", { class: "card" }, h("div", { class: "card-head" }, h("div", null, h("h2", null, "Description"), h("p", null, "Station description, genres and website."))),
        h("div", { class: "card-body stack" }, field("Short description", f.short_description, { max: 180 }), field("Long description", f.long_description, { max: 1200 }),
          field("Website", f.website), field("Genres", genres.el)))),
    h("div", { class: "section-gap" }),
    h("div", { class: "card" }, h("div", { class: "card-head" }, h("div", null, h("h2", null, "Bearers"),
      h("p", null, "Where this station is on air. The first one is the primary SId. Leave ECC/EId empty to use the ensemble's; SCIdS > 0 for secondary components."))),
      h("div", { class: "card-body stack" }, bearers.el, core ? enabled.el : null,
        s.owners ? h("div", { class: "small muted" }, "Station owners: ", s.owners.length ? s.owners.join(", ") : "none - assign them under Users") : null),
      h("div", { class: "card-foot" }, core ? btn("Delete station", { cls: "danger", icon: "trash", onclick: async () => {
        if (!(await confirmDialog(`Delete "${s.medium_name}" with all its logos and EPG entries? It disappears from the carousel at the next Apply.`, { danger: true, okText: "Delete" }))) return;
        try { await api("DELETE", `/api/services/${s.id}`); toast("Station deleted.", "ok"); refreshStatus(); location.hash = "#/stations"; } catch (e) { /* toasted */ }
      } }) : null, h("span", { class: "spacer" }), btn("Save changes", { cls: "primary", icon: "check", onclick: save }))));
}

/* ---------- logos ---------- */

function logoManager(root, ownerId, logos, onChange) {
  const sizes = LOGO_SIZES.map(([w, hh, d]) => [w, hh, d]);
  for (const l of logos) if (!sizes.some(([w, hh]) => w === l.width && hh === l.height)) sizes.push([l.width, l.height, "Custom size (imported)"]);
  put(root, 
    h("div", { class: "banner blue" }, icon("info"), h("div", null,
      "Upload a PNG or JPEG at each exact size, or link a URL. URL logos are re-fetched on the refresh schedule and whenever you Apply; if a URL can't be reached the last good image is kept. ",
      "32×32 is the most important size.")),
    h("div", { class: "section-gap" }),
    h("div", { class: "logo-grid" }, sizes.map(([w, hh, d]) => logoSlot(ownerId, w, hh, d, logos.find((l) => l.width === w && l.height === hh), onChange))));
}

function logoSlot(ownerId, w, hh, desc, logo, onChange) {
  const spec = `${w}x${hh}`;
  const fileInput = h("input", { type: "file", accept: "image/png,image/jpeg", class: "hidden" });
  const upload = async (file, fit = false) => {
    const fd = new FormData(); fd.append("file", file); if (fit) fd.append("fit", "1");
    try {
      await api("POST", `/api/logos/${ownerId}/${spec}/upload`, fd, { form: true, quiet: true });
      toast(`${spec} logo uploaded.`, "ok"); refreshStatus(); onChange();
    } catch (e) {
      if (/expected/.test(e.message) && !fit) {
        if (await confirmDialog(`${e.message} Scale it to fit ${w}×${hh} (letterboxed, aspect ratio kept)?`, { okText: "Scale to fit", title: "Wrong size" })) upload(file, true);
      } else toast(e.message, "error");
    }
  };
  fileInput.addEventListener("change", () => { if (fileInput.files[0]) upload(fileInput.files[0]); fileInput.value = ""; });
  const preview = h("div", { class: "logo-preview" });
  if (logo && logo.file) preview.appendChild(h("img", { src: "/media/" + logo.file, alt: `${spec} logo`, class: w <= 128 ? "pixel" : "" }));
  else preview.appendChild(h("div", { class: "placeholder" }, icon("image"), logo && logo.source === "url" ? "Not fetched yet" : "Drop an image here"));
  const meta = h("div", { class: "logo-meta" },
    h("div", { class: "title" }, h("b", null, `${w} × ${hh}`), h("span", { class: "spacer" }),
      logo ? (logo.source === "url" ? h("span", { class: "chip blue" }, icon("link"), "URL") : h("span", { class: "chip" }, icon("upload"), "Uploaded")) : h("span", { class: "chip" }, "Empty")),
    h("div", { class: "small muted" }, desc),
    logo && logo.source === "url" ? h("div", { class: "url" }, logo.url) : null,
    logo && logo.source === "url" && logo.fetched_at ? h("div", { class: "small muted" }, `Checked ${fmtAgo(logo.fetched_at)}`, logo.fetch_status === "ok" ? " · OK" : "") : null,
    logo && logo.fetch_error ? h("div", { class: "err" }, logo.fetch_error) : null,
    logo && logo.file ? h("div", { class: "small muted" }, `${logo.mime === "image/png" ? "PNG" : "JPEG"} · ${fmtBytes(logo.size)}`) : null);
  const actions = h("div", { class: "logo-actions" },
    btn("Upload", { cls: "sm", icon: "upload", onclick: () => fileInput.click() }),
    btn(logo && logo.source === "url" ? "Change URL" : "Use URL", { cls: "sm", icon: "link", onclick: () => setUrl() }),
    logo && logo.source === "url" ? btn("Fetch now", { cls: "sm ghost", icon: "refresh", onclick: async () => {
      try { const r = await api("POST", `/api/logos/${ownerId}/${spec}/refresh`, {}); toast(r.ok ? "Fetched." : "Fetch failed: " + r.error, r.ok ? "ok" : "error"); onChange(); } catch (e) { /* toasted */ }
    } }) : null,
    logo ? btn("Remove", { cls: "sm ghost danger", icon: "trash", onclick: async () => {
      if (!(await confirmDialog(`Remove the ${spec} logo?`, { danger: true, okText: "Remove" }))) return;
      try { await api("DELETE", `/api/logos/${ownerId}/${spec}`); refreshStatus(); onChange(); } catch (e) { /* toasted */ }
    } }) : null, fileInput);
  const slot = h("div", { class: "logo-slot" }, preview, meta, actions);
  slot.addEventListener("dragover", (e) => { e.preventDefault(); slot.classList.add("drag"); });
  slot.addEventListener("dragleave", () => slot.classList.remove("drag"));
  slot.addEventListener("drop", (e) => { e.preventDefault(); slot.classList.remove("drag"); if (e.dataTransfer.files[0]) upload(e.dataTransfer.files[0]); });

  function setUrl() {
    const u = inp(logo && logo.source === "url" ? logo.url : "", { type: "url", placeholder: `https://example.com/logo-${spec}.png` });
    const m = modal({
      title: `Logo URL · ${w}×${hh}`,
      body: h("div", { class: "stack" }, field("Image URL", u, { hint: `Must serve a ${w}×${hh} PNG or JPEG. Fetched now, on the refresh schedule and on every Apply.` })),
      foot: [btn("Cancel", { onclick: () => m.close() }), btn("Save & fetch", { cls: "primary", onclick: async () => {
        try {
          const r = await api("PUT", `/api/logos/${ownerId}/${spec}/url`, { url: u.value });
          m.close();
          toast(r.ok ? "Logo fetched." : "Saved, but the fetch failed: " + r.error, r.ok ? "ok" : "error");
          refreshStatus(); onChange();
        } catch (e) { /* toasted */ }
      } })],
    });
  }
  return slot;
}

/* ---------- EPG ---------- */

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

async function stationEpg(root, s) {
  const [entries, preview, templates] = await Promise.all([api("GET", `/api/services/${s.id}/programmes`),
    api("GET", `/api/services/${s.id}/epg/preview`), api("GET", "/api/feed-templates")]);
  const en = toggle("Broadcast EPG for this station", s.epg_enabled);
  const feedUrl = inp(s.epg_feed_url, { type: "url", placeholder: "https://example.com/epg.xml" });
  const feedType = sel(s.epg_feed_type, [["xmltv", "XMLTV"], ["spi", "SPI / RadioDNS PI XML"],
    ...templates.map((t) => [`tpl:${t.id}`, `API template: ${t.name}`])]);
  const feedChan = inp(s.epg_feed_channel, { placeholder: "e.g. station.example" });
  const chanField = field("Channel id (XMLTV)", feedChan);
  const feedHint = h("div", { class: "small muted" });
  const syncFeedType = () => {
    const tpl = templates.find((t) => `tpl:${t.id}` === feedType.value);
    chanField.classList.toggle("hidden", feedType.value !== "xmltv");
    feedUrl.placeholder = tpl ? (tpl.definition.example_url || "https://example.com/api/schedule") : "https://example.com/epg.xml";
    feedHint.textContent = tpl ? `${tpl.definition.description} ${FETCH_HELP[tpl.definition.fetch] || ""}` : "";
  };
  feedType.addEventListener("change", syncFeedType);
  syncFeedType();
  const saveFeed = async () => {
    try {
      await api("PUT", `/api/services/${s.id}/epg`, { epg_enabled: en.box.checked, epg_feed_url: feedUrl.value, epg_feed_type: feedType.value, epg_feed_channel: feedChan.value });
      if (feedUrl.value) {
        const r = await api("POST", `/api/services/${s.id}/epg/refresh`, {});
        toast(r.ok ? "EPG settings saved and feed fetched." : "Saved, but the feed failed: " + r.error, r.ok ? "ok" : "error");
      } else toast("EPG settings saved.", "ok");
      refreshStatus(); route();
    } catch (e) { /* toasted */ }
  };
  const week = h("div", { class: "week" }, preview.days.map((d) => {
    const dt = new Date(d.date + "T12:00:00");
    return h("div", { class: "week-day" }, h("h4", null, dt.toLocaleDateString(undefined, { weekday: "short" }), " ", h("b", null, dt.getDate())),
      d.programmes.length ? d.programmes.map((p) => h("div", { class: "prog" + (p.source === "feed" ? " feed" : ""), title: p.description || p.title },
        h("span", { class: "t" }, `${p.start}–${p.end}`), h("b", null, p.title))) : h("span", { class: "small muted" }, "Nothing scheduled"));
  }));
  const tbody = h("tbody");
  for (const e of entries) {
    const when = e.kind === "weekly" ? (e.days === 127 ? "Every day" : e.days === 31 ? "Weekdays" : e.days === 96 ? "Weekends" : DAYS.filter((_, i) => (e.days >> i) & 1).join(", ")) : e.date;
    tbody.appendChild(h("tr", { class: "click", onclick: () => programmeEditor(s, e) },
      h("td", null, h("b", null, e.title), e.description ? h("div", { class: "small muted ellipsis" }, e.description) : null),
      h("td", { class: "nowrap" }, when), h("td", { class: "mono nowrap" }, e.start_time), h("td", { class: "nowrap" }, `${e.duration} min`),
      h("td", null, e.kind === "weekly" ? h("span", { class: "chip accent" }, "Weekly") : h("span", { class: "chip" }, "One-off"))));
  }
  put(root, 
    h("div", { class: "grid-2" },
      h("div", { class: "card" }, h("div", { class: "card-head" }, h("div", null, h("h2", null, "EPG broadcast"), h("p", null, `Sends the next ${preview.days.length} days of programme information. Times are in ${preview.timezone}.`))),
        h("div", { class: "card-body stack" }, en.el,
          h("div", { class: "small muted" }, "Hand-entered programmes take priority; feed programmes fill the gaps.")),
        h("div", { class: "card-foot" }, btn("Save", { cls: "primary", onclick: saveFeed }))),
      h("div", { class: "card" }, h("div", { class: "card-head" }, h("div", null, h("h2", null, "Schedule feed (optional)"), h("p", null, "Import programmes from XMLTV, SPI XML or any JSON API through a template, refreshed with the logos."))),
        h("div", { class: "card-body stack" }, field("Format", feedType, { hint: isEditor() ? "API templates are managed under EPG templates." : null }),
          field("Feed URL", feedUrl), feedHint, chanField,
          s.epg_feed_status ? h("div", { class: "small " + (s.epg_feed_status.startsWith("error") ? "chip red" : "muted") }, s.epg_feed_status, s.epg_feed_checked ? ` · ${fmtAgo(s.epg_feed_checked)}` : "") : null),
        h("div", { class: "card-foot" }, btn("Save & fetch", { cls: "primary", onclick: saveFeed })))),
    h("div", { class: "section-gap" }),
    h("div", { class: "card" }, h("div", { class: "card-head" }, h("div", { class: "grow" }, h("h2", null, "Programmes"), h("p", null, "Recurring weekly shows and one-off programmes.")),
      btn("Add programme", { cls: "primary", icon: "plus", onclick: () => programmeEditor(s, null) })),
      entries.length ? h("div", { class: "table-wrap" }, h("table", null, h("thead", null, h("tr", null, h("th", null, "Programme"), h("th", null, "When"), h("th", null, "Start"), h("th", null, "Length"), h("th", null, "Type"))), tbody))
        : h("div", { class: "card-body muted" }, "No programmes yet.")),
    h("div", { class: "section-gap" }),
    h("div", { class: "card" }, h("div", { class: "card-head" }, h("div", null, h("h2", null, "Preview"), h("p", null, "What receivers will see (hand-entered in teal, feed in blue)."))),
      h("div", { class: "card-body" }, week)));
}

function programmeEditor(s, e) {
  const isNew = !e;
  e = e || { kind: "weekly", days: 31, start_time: "07:00", duration: 60, title: "", short_title: "", description: "", genres: [], date: "", valid_from: "", valid_to: "" };
  let days = e.days || 0;
  const kind = h("div", { class: "segmented" });
  let k = e.kind;
  const title = inp(e.title, { maxlength: 128 }), st = inp(e.short_title, { maxlength: 8 });
  const desc = h("textarea", { rows: 3 }, e.description);
  const start = h("input", { type: "time", value: e.start_time });
  const dur = h("input", { type: "number", min: 1, max: 1440, value: e.duration });
  const date = h("input", { type: "date", value: e.date });
  const vf = h("input", { type: "date", value: e.valid_from }), vt = h("input", { type: "date", value: e.valid_to });
  const dayPick = h("div", { class: "days-pick" });
  const genres = genrePicker(e.genres || [], false);
  const weeklyBox = h("div", { class: "stack" }), onceBox = h("div", { class: "stack" });
  const drawDays = () => { clear(dayPick); DAYS.forEach((d, i) => dayPick.appendChild(h("button", { type: "button", class: (days >> i) & 1 ? "on" : "", onclick: () => { days ^= 1 << i; drawDays(); } }, d))); };
  const drawKind = () => {
    clear(kind);
    [["weekly", "Weekly"], ["once", "One-off"]].forEach(([v, l]) => kind.appendChild(h("button", { type: "button", class: k === v ? "on" : "", onclick: () => { k = v; drawKind(); } }, l)));
    weeklyBox.classList.toggle("hidden", k !== "weekly"); onceBox.classList.toggle("hidden", k !== "once");
  };
  put(weeklyBox, field("Days", dayPick), h("div", { class: "grid-2" }, field("Starting from (optional)", vf), field("Until (optional)", vt)));
  put(onceBox, field("Date", date));
  drawDays(); drawKind();
  const m = modal({
    title: isNew ? "Add programme" : "Edit programme", wide: true,
    body: h("div", { class: "stack" }, kind, h("div", { class: "grid-2" }, field("Title", title, { max: 128 }), field("Short title (optional)", st, { max: 8 })),
      weeklyBox, onceBox, h("div", { class: "grid-2" }, field("Start time", start), field("Duration (minutes)", dur)),
      field("Description", desc, { max: 1200 }), field("Genres", genres.el)),
    foot: [isNew ? null : btn("Delete", { cls: "danger", icon: "trash", onclick: async () => {
      if (!(await confirmDialog(`Delete "${e.title}"?`, { danger: true, okText: "Delete" }))) return;
      try { await api("DELETE", `/api/programmes/${e.id}`); m.close(); refreshStatus(); route(); } catch (ex) { /* toasted */ }
    } }), h("span", { class: "spacer" }), btn("Cancel", { onclick: () => m.close() }), btn("Save", { cls: "primary", onclick: async () => {
      const body = { kind: k, days, title: title.value, short_title: st.value, description: desc.value, start_time: start.value, duration: +dur.value,
        date: date.value, valid_from: vf.value, valid_to: vt.value, genres: genres.get() };
      try {
        if (isNew) await api("POST", `/api/services/${s.id}/programmes`, body); else await api("PUT", `/api/programmes/${e.id}`, body);
        m.close(); refreshStatus(); route();
      } catch (ex) { /* toasted */ }
    } })],
  });
}

/* ============================== ensemble ============================== */

async function pageEnsemble(root) {
  setCrumbs("Ensemble");
  const { ensemble, logos, editable } = await api("GET", "/api/ensemble");
  const ecc = inp(ensemble.ecc, { class: "mono", maxlength: 2, disabled: !editable });
  const eid = inp(ensemble.eid, { class: "mono", maxlength: 4, disabled: !editable });
  const ln = inp(ensemble.medium_name, { disabled: !editable });
  const sn = inp(ensemble.short_name, { disabled: !editable });
  const logoBox = h("div");
  put(root, 
    h("div", { class: "page-head" }, logoTile(ensemble.medium_name, logos, true), h("div", null, h("h1", null, ensemble.medium_name || "Ensemble"),
      h("p", null, ensemble.ecc && ensemble.eid ? `ECC ${ensemble.ecc.toUpperCase()} · EId ${ensemble.eid.toUpperCase()}` : "Not configured"))),
    h("div", { class: "card" }, h("div", { class: "card-head" }, h("div", null, h("h2", null, "Identity"), h("p", null, "Must match the ensemble block of your odr-dabmux configuration."))),
      h("div", { class: "card-body grid-4" }, field("ECC", ecc), field("EId", eid), field("Label", ln, { max: 16 }), field("Short label", sn, { max: 8 })),
      editable ? h("div", { class: "card-foot" }, btn("Save", { cls: "primary", onclick: async () => {
        try { await api("PUT", "/api/ensemble", { ecc: ecc.value, eid: eid.value, medium_name: ln.value, short_name: sn.value }); toast("Saved - click Apply to publish.", "ok"); refreshStatus(); route(); } catch (e) { /* toasted */ }
      } })) : null),
    h("div", { class: "section-gap" }), h("h2", null, "Ensemble logos"), h("div", { class: "section-gap" }), logoBox);
  if (editable) logoManager(logoBox, 0, logos, () => route());
  else logoBox.appendChild(h("div", { class: "logo-grid" }, logos.map((l) => h("div", { class: "logo-slot" },
    h("div", { class: "logo-preview" }, l.file ? h("img", { src: "/media/" + l.file, alt: "" }) : null), h("div", { class: "logo-meta" }, h("b", null, `${l.width} × ${l.height}`))))));
}

/* ============================== activity ============================== */

async function pageActivity(root) {
  setCrumbs("Activity");
  const [builds, st] = await Promise.all([api("GET", "/api/builds"), api("GET", "/api/status")]);
  const last = builds[0];
  const statusPill = (b) => b.status === "ok" ? h("span", { class: "pill green" }, "OK") : b.status === "warning" ? h("span", { class: "pill amber" }, "Warnings")
    : b.status === "running" ? h("span", { class: "pill muted" }, "Running") : h("span", { class: "pill red" }, "Failed");
  put(root, h("div", { class: "page-head" }, h("div", null, h("h1", null, "Activity"), h("p", null, "Carousel builds - on Apply, on the refresh schedule, and at start-up.")),
    h("span", { class: "spacer" }), st.can_apply ? btn("Apply now", { cls: "primary", icon: "zap", onclick: applyChanges }) : null));
  if (last) {
    const s = last.stats || {};
    put(root, h("div", { class: "card" },
      h("div", { class: "card-head" }, h("div", { class: "grow" }, h("h2", null, "Latest build"), h("p", null, `${fmtDate(last.started_at)} · ${last.trigger}${last.username ? " by " + last.username : ""}`)), statusPill(last)),
      h("div", { class: "card-body stack" },
        last.message ? h("div", { class: "mono small" }, last.message) : null,
        s.stream_bytes ? h("div", { class: "stats" },
          h("div", { class: "stat" }, h("span", null, "Stations"), h("b", null, s.services)),
          h("div", { class: "stat" }, h("span", null, "Logo objects"), h("b", null, s.logos)),
          h("div", { class: "stat" }, h("span", null, "EPG objects"), h("b", null, s.epg_objects)),
          h("div", { class: "stat" }, h("span", null, "Stream size"), h("b", null, fmtBytes(s.stream_bytes))),
          h("div", { class: "stat" }, h("span", null, `Cycle time @ ${s.bitrate} kbps`), h("b", null, fmtMinSec(s.cycle_seconds)))) : null,
        last.warnings && last.warnings.length ? h("div", { class: "banner amber" }, icon("alert"), h("div", { class: "grow" },
          h("div", { class: "row" }, h("b", null, `${last.warnings.length} warning(s)`), h("span", { class: "spacer" }),
            isEditor() && last.warnings.length > 1 ? btn("Dismiss all", { cls: "sm", onclick: () => dismissWarning(last.id, null) }) : null),
          h("ul", { class: "warn-list" }, last.warnings.map((w) => h("li", null, h("span", null, w),
            isEditor() ? btn("Dismiss", { cls: "sm", title: "Hide this warning on future builds too", onclick: () => dismissWarning(last.id, w) }) : null))))) : null,
        s.dismissed_warnings && isEditor() ? h("div", { class: "small muted row" }, `${s.dismissed_warnings} dismissed warning(s) hidden.`,
          btn("Show them again", { cls: "sm ghost", onclick: async () => {
            try { await api("POST", "/api/warnings/restore", {}); toast("Dismissed warnings will show again from the next build.", "ok"); } catch (e) { /* toasted */ }
          } })) : null,
        h("div", { class: "small muted" }, "Next scheduled refresh: ", st.next_refresh ? `${fmtDate(st.next_refresh)} (${fmtIn(st.next_refresh)})` : "—"))));
    put(root, h("div", { class: "section-gap" }));
  }
  put(root, h("div", { class: "card" }, h("div", { class: "card-head" }, h("h2", null, "History")),
    builds.length ? h("div", { class: "table-wrap" }, h("table", null, h("thead", null, h("tr", null, h("th", null, "When"), h("th", null, "Trigger"), h("th", null, "Status"), h("th", null, "Size"), h("th", null, "Details"))),
      h("tbody", null, builds.map((b) => h("tr", null, h("td", { class: "nowrap" }, fmtDate(b.started_at)), h("td", null, b.trigger, b.username ? h("span", { class: "muted" }, " · " + b.username) : null),
        h("td", null, statusPill(b)), h("td", { class: "nowrap" }, b.stats && b.stats.stream_bytes ? fmtBytes(b.stats.stream_bytes) : "—"),
        h("td", { class: "small" }, b.message, b.warnings && b.warnings.length ? h("span", { class: "muted" }, ` · ${b.warnings.length} warning(s)`) : null))))))
      : h("div", { class: "card-body muted" }, "Nothing published yet - make your changes and click Apply.")));
}

/* ============================== import ============================== */

function pageImport(root) {
  setCrumbs("Import");
  const area = h("div");
  const start = () => {
    clear(area);
    const xmlFile = h("input", { type: "file", accept: ".xml,application/xml,text/xml" });
    const muxFile = h("input", { type: "file", accept: ".info,.conf,.ini,.cfg,.mux,text/plain" });
    put(area, h("div", { class: "grid-2" },
      h("div", { class: "card" }, h("div", { class: "card-head" }, h("div", null, h("h2", null, "Legacy SPI / XSI XML"), h("p", null, "serviceInformation XML from RadioDNS XSI generators or the old hybridspi tools - names, descriptions, genres, bearers and logos."))),
        h("div", { class: "card-body stack" }, field("XML file", xmlFile)),
        h("div", { class: "card-foot" }, btn("Read file", { cls: "primary", icon: "upload", onclick: async () => {
          if (!xmlFile.files[0]) return toast("Choose an XML file.", "error");
          const fd = new FormData(); fd.append("file", xmlFile.files[0]);
          try { showImport(await api("POST", "/api/import/legacy", fd, { form: true })); } catch (e) { /* toasted */ }
        } }))),
      h("div", { class: "card" }, h("div", { class: "card-head" }, h("div", null, h("h2", null, "ODR-DabMux configuration"), h("p", null, "Create stations from the audio services in your odr-dabmux config (labels, SIds, ECCs)."))),
        h("div", { class: "card-body stack" }, field("Config file", muxFile)),
        h("div", { class: "card-foot" },
          isAdmin() ? btn("Choose on server…", { icon: "folder", onclick: async () => {
            const p = await fileBrowser({ title: "Select odr-dabmux config", mode: "file", exts: "info,conf,ini,cfg,mux", start: "/home" });
            if (!p) return;
            const fd = new FormData(); fd.append("path", p);
            try { showImport(await api("POST", "/api/import/dabmux", fd, { form: true })); } catch (e) { /* toasted */ }
          } }) : null,
          btn("Read file", { cls: "primary", icon: "upload", onclick: async () => {
            if (!muxFile.files[0]) return toast("Choose a config file.", "error");
            const fd = new FormData(); fd.append("file", muxFile.files[0]);
            try { showImport(await api("POST", "/api/import/dabmux", fd, { form: true })); } catch (e) { /* toasted */ }
          } })))));
  };
  const showImport = (imp) => {
    clear(area);
    const missing = imp.local_logos.filter((l) => !l.matched);
    const folderInput = h("input", { type: "file", multiple: true, class: "hidden" });
    folderInput.setAttribute("webkitdirectory", "");
    folderInput.addEventListener("change", async () => {
      const fd = new FormData();
      let n = 0;
      for (const f of folderInput.files) {
        if (!/\.(png|jpe?g)$/i.test(f.name) || f.size > 2 * 1024 * 1024) continue;
        fd.append("files", f, f.webkitRelativePath || f.name); n++;
      }
      if (!n) return toast("No PNG/JPEG files found in that folder.", "error");
      toast(`Uploading ${n} images…`);
      try { showImport(await api("POST", `/api/import/${imp.id}/files`, fd, { form: true })); } catch (e) { /* toasted */ }
    });
    const mode = sel("merge", [["merge", "Merge - update stations with the same primary SId, add the rest"], ["add", "Add all as new stations"], ["replace", "Replace - delete all existing stations first"]]);
    const ens = toggle(`Also set the ensemble id${imp.ensemble && imp.ensemble.ecc ? ` (${imp.ensemble.ecc}.${imp.ensemble.eid})` : ""}`, false, { disabled: !imp.ensemble || !imp.ensemble.ecc });
    put(area, 
      h("div", { class: "card" }, h("div", { class: "card-head" }, h("div", { class: "grow" }, h("h2", null, `${imp.services.length} station(s) found`),
        h("p", null, imp.ensemble && imp.ensemble.ecc ? `Ensemble ${imp.ensemble.ecc}.${imp.ensemble.eid}` : "No ensemble id in file")), btn("Start over", { cls: "ghost", onclick: start })),
        h("div", { class: "table-wrap" }, h("table", null, h("thead", null, h("tr", null, h("th", null, "Station"), h("th", null, "Primary SId"), h("th", null, "Bearers"), h("th", null, "Logos"), h("th", null, "Genres"), h("th", null, ""))),
          h("tbody", null, imp.services.map((s) => h("tr", null, h("td", null, h("b", null, s.medium_name), h("span", { class: "muted" }, "  " + s.short_name)),
            h("td", { class: "mono" }, s.sid ? s.sid.toUpperCase() : "—"), h("td", null, s.bearers), h("td", null, s.logos), h("td", null, s.genres),
            h("td", null, s.exists ? h("span", { class: "chip amber" }, "exists") : h("span", { class: "chip green" }, "new")))))))),
      h("div", { class: "section-gap" }),
      imp.fixes.length ? h("div", { class: "banner green" }, icon("check"), h("div", null, h("b", null, "Fixed text encoding"), h("ul", null, imp.fixes.map((f) => h("li", null, f))))) : null,
      imp.warnings.length ? h("div", { class: "banner amber" }, icon("alert"), h("div", null, h("b", null, "Warnings"), h("ul", null, imp.warnings.map((f) => h("li", null, f))))) : null,
      imp.remote_logos ? h("div", { class: "banner blue" }, icon("link"), `${imp.remote_logos} logo(s) use http(s) URLs - they will be fetched after import and kept up to date on the refresh schedule.`) : null,
      h("div", { class: "section-gap" }),
      imp.local_logos.length ? h("div", { class: "card" }, h("div", { class: "card-head" }, h("div", { class: "grow" }, h("h2", null, "Local logo files"),
        h("p", null, `${imp.local_logos.length - missing.length} of ${imp.local_logos.length} found. The XML refers to image files by name - point to the folder they're in and they'll be copied into the generator's storage.`)),
        btn("Upload folder from this computer…", { icon: "upload", onclick: () => folderInput.click() }),
        isAdmin() ? btn("Choose folder on server…", { icon: "folder", onclick: async () => {
          const p = await fileBrowser({ title: "Folder containing the logo files", mode: "dir", start: "/home" });
          if (!p) return;
          try { showImport(await api("POST", `/api/import/${imp.id}/folder`, { path: p })); } catch (e) { /* toasted */ }
        } }) : null, folderInput),
        h("div", { class: "table-wrap" }, h("table", null, h("thead", null, h("tr", null, h("th", null, "Station"), h("th", null, "File"), h("th", null, "Size"), h("th", null, ""))),
          h("tbody", null, imp.local_logos.map((l) => h("tr", null, h("td", null, l.service), h("td", { class: "mono small" }, l.url), h("td", { class: "nowrap" }, `${l.width}×${l.height}`),
            h("td", null, l.matched ? h("span", { class: "chip green" }, icon("check"), "Found") : l.error ? h("span", { class: "chip red", title: l.error }, l.error) : h("span", { class: "chip" }, "Missing")))))))) : null,
      h("div", { class: "section-gap" }),
      h("div", { class: "card" }, h("div", { class: "card-head" }, h("h2", null, "Import")),
        h("div", { class: "card-body stack" }, field("Mode", mode), ens.el,
          missing.length ? h("div", { class: "small muted" }, `${missing.length} logo file(s) not found - those stations are imported without them; you can upload later.`) : null),
        h("div", { class: "card-foot" }, btn("Cancel", { cls: "ghost", onclick: start }), btn(`Import ${imp.services.length} station(s)`, { cls: "primary", icon: "import", onclick: async () => {
          if (mode.value === "replace" && !(await confirmDialog("This deletes every existing station (and its logos and EPG) before importing.", { danger: true, okText: "Replace all" }))) return;
          try {
            const r = await api("POST", `/api/import/${imp.id}/commit`, { mode: mode.value, import_ensemble: ens.box.checked });
            toast(`Imported: ${r.created} new, ${r.updated} updated${r.fetching ? `, fetching ${r.fetching} logo URL(s)` : ""}. Click Apply to publish.`, "ok");
            refreshStatus(); location.hash = "#/stations";
          } catch (e) { /* toasted */ }
        } }))));
  };
  put(root, h("div", { class: "page-head" }, h("div", null, h("h1", null, "Import"), h("p", null, "Bring in stations from existing files."))), area);
  start();
}

/* ============================== mux config ============================== */

function snippetBlocks(sn) {
  const all = Object.entries(sn.blocks).map(([sec, b]) => `${sec} {\n${b.split("\n").map((l) => "    " + l).join("\n")}\n}`).join("\n\n");
  return h("div", { class: "stack" },
    Object.entries(sn.blocks).map(([sec, b]) => h("div", { class: "stack tight" }, h("div", { class: "small muted" }, "Inside the ", h("code", null, sec + " { … }"), " section:"), codeBlock(b))),
    h("details", null, h("summary", { class: "small muted" }, "All three as one block"), h("div", { class: "section-gap" }), codeBlock(all)));
}

async function pageMux(root) {
  setCrumbs("Mux config");
  const sn = await api("GET", "/api/mux-snippet");
  put(root, h("div", { class: "page-head" }, h("div", null, h("h1", null, "Multiplexer configuration"),
    h("p", null, `Example entries for your odr-dabmux config. Packet size ${sn.packet_size} bytes.`))));
  if (isAdmin()) {
    const s = await api("GET", "/api/settings");
    const m = s.mux;
    const f = {
      service_uid: inp(m.service_uid, { class: "mono" }), service_id: inp(m.service_id, { class: "mono", placeholder: "auto: ECC+EId+f1" }),
      label: inp(m.label), short_label: inp(m.short_label), subchannel_uid: inp(m.subchannel_uid, { class: "mono" }),
      subchannel_id: h("input", { type: "number", min: 0, max: 63, value: m.subchannel_id }), component_uid: inp(m.component_uid, { class: "mono" }),
      protection_profile: sel(m.protection_profile, [["EEP_A", "EEP_A"], ["EEP_B", "EEP_B (bitrate multiple of 32)"]]),
      protection: sel(m.protection, [[1, "1 (strongest)"], [2, "2"], [3, "3"], [4, "4 (weakest)"]]),
    };
    put(root, h("div", { class: "card" }, h("div", { class: "card-head" }, h("div", null, h("h2", null, "SPI service settings"), h("p", null, "Used only to build the example below - the generator itself doesn't touch your mux config."))),
      h("div", { class: "card-body stack" },
        h("div", { class: "grid-4" }, field("Service uid", f.service_uid), field("Service id (32-bit)", f.service_id), field("Label", f.label, { max: 16 }), field("Short label", f.short_label, { max: 8 })),
        h("div", { class: "grid-4" }, field("Subchannel uid", f.subchannel_uid), field("Subchannel id", f.subchannel_id, { hint: "Unused id, e.g. last audio id + 1" }), field("Protection profile", f.protection_profile), field("Protection level", f.protection)),
        h("div", { class: "grid-4" }, field("Component uid", f.component_uid))),
      h("div", { class: "card-foot" }, btn("Save", { cls: "primary", onclick: async () => {
        const mux = {}; for (const [k, el] of Object.entries(f)) mux[k] = el.value;
        mux.subchannel_id = +mux.subchannel_id; mux.protection = +mux.protection;
        try { await api("PUT", "/api/settings", { mux }); toast("Saved.", "ok"); route(); } catch (e) { /* toasted */ }
      } }))), h("div", { class: "section-gap" }));
  }
  put(root, h("div", { class: "card" }, h("div", { class: "card-head" }, h("h2", null, "Example entries")),
    h("div", { class: "card-body stack" }, sn.warnings.map((w) => h("div", { class: "banner amber" }, icon("alert"), w)), snippetBlocks(sn))));
}

/* ============================== users ============================== */

async function pageUsers(root) {
  setCrumbs("Users");
  const [users, services] = await Promise.all([api("GET", "/api/users"), api("GET", "/api/services")]);
  const svcName = Object.fromEntries(services.map((s) => [s.id, s.medium_name]));
  put(root, h("div", { class: "page-head" }, h("div", null, h("h1", null, "Users"),
    h("p", null, "Administrators manage everything. Editors manage all stations. Station owners can update branding, descriptions and EPG for the stations assigned to them.")),
    h("span", { class: "spacer" }), btn("Add user", { cls: "primary", icon: "plus", onclick: () => userEditor(null, services) })),
  h("div", { class: "card" }, h("div", { class: "table-wrap" }, h("table", null,
    h("thead", null, h("tr", null, h("th", null, "User"), h("th", null, "Role"), h("th", null, "Stations"), h("th", null, "Can apply"), h("th", null, "Status"), h("th", null, "Last login"))),
    h("tbody", null, users.map((u) => h("tr", { class: "click", onclick: () => userEditor(u, services) },
      h("td", null, h("div", { class: "row" }, h("span", { class: "avatar" }, initials(u.display_name || u.username)), h("div", null, h("b", null, u.display_name || u.username), h("div", { class: "small muted" }, u.username)))),
      h("td", null, h("span", { class: "chip " + (u.role === "admin" ? "accent" : u.role === "editor" ? "blue" : "") }, ROLE_LABEL[u.role])),
      h("td", { class: "small" }, u.role === "station" ? (u.services.map((id) => svcName[id]).filter(Boolean).join(", ") || h("span", { class: "muted" }, "none")) : h("span", { class: "muted" }, "all")),
      h("td", null, u.role !== "station" || u.can_apply ? icon("check") : h("span", { class: "muted" }, "—")),
      h("td", null, u.disabled ? h("span", { class: "chip red" }, "Disabled") : u.locked ? h("span", { class: "chip amber" }, "Locked") : u.must_change_pw ? h("span", { class: "chip" }, "Temp. password") : h("span", { class: "chip green" }, "Active")),
      h("td", { class: "small muted nowrap" }, fmtAgo(u.last_login)))))))));
}

function userEditor(u, services) {
  const isNew = !u;
  u = u || { username: "", display_name: "", role: "station", can_apply: 0, disabled: 0, services: [] };
  const username = inp(u.username, { disabled: !isNew, autocomplete: "off" });
  const dn = inp(u.display_name);
  const role = sel(u.role, [["station", "Station owner"], ["editor", "Editor"], ["admin", "Administrator"]]);
  const pw = h("input", { type: "password", autocomplete: "new-password", placeholder: "Leave empty to generate one" });
  const canApply = toggle("Can publish (Apply) changes", !!u.can_apply);
  const disabled = toggle("Account disabled", !!u.disabled);
  const picks = new Set(u.services);
  const svcList = h("div", { class: "list-check" }, services.length ? services.map((s) => {
    const t = toggle(s.medium_name + (s.bearers[0] ? `  ·  ${s.bearers[0].sid.toUpperCase()}` : ""), picks.has(s.id));
    t.box.addEventListener("change", () => (t.box.checked ? picks.add(s.id) : picks.delete(s.id)));
    return t.el;
  }) : h("span", { class: "muted small" }, "No stations yet."));
  const stationBox = h("div", { class: "stack" }, field("Stations this user can manage", svcList), canApply.el);
  const syncRole = () => stationBox.classList.toggle("hidden", role.value !== "station");
  role.addEventListener("change", syncRole); syncRole();
  const m = modal({
    title: isNew ? "Add user" : `Edit ${u.username}`, wide: true,
    body: h("div", { class: "stack" }, h("div", { class: "grid-2" }, field("Username", username), field("Display name", dn)),
      h("div", { class: "grid-2" }, field("Role", role), isNew ? field("Initial password", pw, { hint: "They must change it at first login." }) : h("div")),
      stationBox, isNew ? null : disabled.el,
      isNew ? null : h("div", { class: "row wrap" },
        btn("Reset password", { cls: "sm", icon: "lock", onclick: async () => {
          if (!(await confirmDialog(`Generate a new temporary password for ${u.username}? Their sessions are signed out.`, { okText: "Reset" }))) return;
          try { const r = await api("POST", `/api/users/${u.id}/reset-password`, {}); showSecret("Temporary password", `Give this to ${u.username}. They must change it at next login.`, r.password); } catch (e) { /* toasted */ }
        } }),
        u.locked ? btn("Unlock", { cls: "sm", onclick: async () => { try { await api("PATCH", `/api/users/${u.id}`, { unlock: true }); toast("Unlocked.", "ok"); m.close(); route(); } catch (e) { /* toasted */ } } }) : null)),
    foot: [isNew ? null : btn("Delete", { cls: "danger", icon: "trash", onclick: async () => {
      if (!(await confirmDialog(`Delete user ${u.username}?`, { danger: true, okText: "Delete" }))) return;
      try { await api("DELETE", `/api/users/${u.id}`); m.close(); route(); } catch (e) { /* toasted */ }
    } }), h("span", { class: "spacer" }), btn("Cancel", { onclick: () => m.close() }), btn(isNew ? "Create user" : "Save", { cls: "primary", onclick: async () => {
      const body = { display_name: dn.value, role: role.value, can_apply: canApply.box.checked, services: [...picks] };
      try {
        if (isNew) {
          const r = await api("POST", "/api/users", { ...body, username: username.value, password: pw.value });
          m.close();
          if (r.password) showSecret("User created", `Give this temporary password to ${username.value}. They must change it at first login.`, r.password);
          else toast("User created.", "ok");
        } else {
          await api("PATCH", `/api/users/${u.id}`, { ...body, disabled: disabled.box.checked });
          m.close(); toast("Saved.", "ok");
        }
        route();
      } catch (e) { /* toasted */ }
    } })],
  });
}

/* ============================== EPG API templates ============================== */

const FETCH_MODES = [["per_weekday", "One request per weekday"], ["per_date", "One request per date"], ["once", "One request for the whole week"]];
const FETCH_HELP = {
  per_weekday: "Paste the URL for any one day: the day is replaced for each weekday on every refresh.",
  per_date: "Paste the URL for any one date: the date is replaced for each of the next days on every refresh.",
  once: "One request covers the whole week.",
};
const TIME_FORMATS = [["clock", "Clock time on that day (HH:MM or HH:MM:SS, 24:00 = midnight)"], ["datetime", "Local date and time (YYYY-MM-DD HH:MM:SS)"],
  ["iso", "ISO 8601 with offset (2026-10-27T07:00:00+01:00)"], ["unix", "Unix timestamp (seconds)"]];
const BLANK_TEMPLATE = { name: "", description: "", example_url: "", fetch: "per_weekday", day_param: "day", day_value: "{weekday}",
  items_path: "", title: "title", description_field: "description", start: "start", end: "end", duration: "", days: "", time_format: "clock" };

async function pageTemplates(root) {
  setCrumbs("EPG templates");
  const tpls = await api("GET", "/api/feed-templates");
  put(root,
    h("div", { class: "page-head" }, h("div", null, h("h1", null, "EPG API templates"),
      h("p", null, "Recipes for reading programme schedules from JSON APIs. Pick one per station on its EPG tab; the station supplies the URL.")),
      h("span", { class: "spacer" }),
      btn("Restore samples", { icon: "refresh", onclick: async () => {
        try { const r = await api("POST", "/api/feed-templates/restore-samples", {}); toast(r.added ? `Restored ${r.added} sample(s).` : "All samples are present.", "ok"); route(); } catch (e) { /* toasted */ }
      } }),
      btn("Import JSON", { icon: "import", onclick: importTemplate }),
      btn("New template", { cls: "primary", icon: "plus", onclick: () => templateEditor(null) })),
    h("div", { class: "card" }, tpls.length ? h("div", { class: "table-wrap" }, h("table", null,
      h("thead", null, h("tr", null, h("th", null, "Template"), h("th", null, "Requests"), h("th", null, "Used by"), h("th", null, ""))),
      h("tbody", null, tpls.map((t) => h("tr", { class: "click", onclick: () => templateEditor(t) },
        h("td", null, h("div", { class: "row" }, h("b", null, t.name), t.sample ? h("span", { class: "chip accent" }, "Sample") : null),
          h("div", { class: "small muted" }, t.definition.description)),
        h("td", { class: "nowrap small" }, (FETCH_MODES.find((m) => m[0] === t.definition.fetch) || [, ""])[1]),
        h("td", { class: "nowrap" }, t.used_by ? `${t.used_by} station(s)` : h("span", { class: "muted" }, "—")),
        h("td", { class: "nowrap" }, iconBtn("copy", "Copy as JSON", (e) => { e.stopPropagation(); copyText(JSON.stringify(t.definition, null, 2)); }),
          iconBtn("plus", "Duplicate", (e) => { e.stopPropagation(); templateEditor({ definition: { ...t.definition, name: `${t.definition.name} (copy)` } }); })))))))
      : h("div", { class: "card-body muted" }, "No templates - add one or restore the samples.")));
}

function importTemplate() {
  const ta = h("textarea", { rows: 14, class: "mono", placeholder: '{ "name": "My station API", "fetch": "per_weekday", ... }' });
  const m = modal({
    title: "Import template JSON", wide: true,
    body: h("div", { class: "stack" }, h("p", { class: "muted" }, "Paste a template copied with the copy button on another installation."), ta),
    foot: [btn("Cancel", { onclick: () => m.close() }), btn("Open in editor", { cls: "primary", onclick: () => {
      let d;
      try { d = JSON.parse(ta.value); } catch (e) { return toast("That isn't valid JSON.", "error"); }
      if (!d || typeof d !== "object" || Array.isArray(d)) return toast("Expected a JSON object.", "error");
      m.close(); templateEditor({ definition: { ...BLANK_TEMPLATE, ...d } });
    } })],
  });
}

function templateEditor(t) {
  const isNew = !t || !t.id;
  const d = { ...BLANK_TEMPLATE, ...((t && t.definition) || {}) };
  const f = {
    name: inp(d.name, { maxlength: 64 }), description: inp(d.description, { maxlength: 500 }),
    example_url: inp(d.example_url, { type: "url", maxlength: 500, placeholder: "https://example.com/api/schedule?day=Monday" }),
    fetch: sel(d.fetch, FETCH_MODES), day_param: inp(d.day_param, { class: "mono", placeholder: "day" }),
    day_value: inp(d.day_value, { class: "mono", placeholder: "{weekday}" }), items_path: inp(d.items_path, { class: "mono", placeholder: "(response is the list)" }),
    title: inp(d.title, { class: "mono" }), description_field: inp(d.description_field, { class: "mono" }),
    start: inp(d.start, { class: "mono" }), end: inp(d.end, { class: "mono" }), duration: inp(d.duration, { class: "mono", placeholder: "(optional, seconds)" }),
    days: inp(d.days, { class: "mono", placeholder: "(optional)" }), time_format: sel(d.time_format, TIME_FORMATS),
  };
  const collect = () => Object.fromEntries(Object.entries(f).map(([k, el]) => [k, el.value.trim()]));
  const dayBox = h("div", { class: "grid-2" }, field("Day query parameter", f.day_param, { hint: "Set on the URL for each day, or put {day} in the URL instead." }),
    field("Day value", f.day_value, { hint: "{weekday} Monday · {weekday_lower} monday · {weekday_short} Mon · {weekday_num} 1-7 · {date} 2026-10-27 · {yyyymmdd}" }));
  const syncFetch = () => dayBox.classList.toggle("hidden", f.fetch.value === "once");
  f.fetch.addEventListener("change", syncFetch); syncFetch();

  const testUrl = inp(d.example_url, { type: "url", placeholder: "URL to test with" });
  const results = h("div", { class: "stack" });
  const runTest = async () => {
    clear(results).appendChild(h("div", { class: "row muted" }, h("span", { class: "spin" }), "Fetching…"));
    try {
      const r = await api("POST", "/api/feed-templates/test", { definition: collect(), url: testUrl.value }, { quiet: true });
      clear(results);
      put(results, h("div", { class: r.count ? "banner green" : "banner amber" }, icon(r.count ? "check" : "alert"),
        h("div", null, r.count ? `${r.count} programme(s) over the next 7 days (${r.requests.length} request(s), times in ${r.timezone}).`
          : "The request worked but no programmes matched - check the items path and field names.")),
      r.programmes.length ? h("div", { class: "table-wrap" }, h("table", null, h("thead", null, h("tr", null, h("th", null, "Start"), h("th", null, "End"), h("th", null, "Title"), h("th", null, "Description"))),
        h("tbody", null, r.programmes.map((p) => h("tr", null, h("td", { class: "mono small nowrap" }, fmtLocal(p.start)), h("td", { class: "mono small nowrap" }, fmtLocal(p.end)),
          h("td", null, p.title), h("td", { class: "small muted" }, p.description)))))) : null,
      h("details", null, h("summary", { class: "small muted" }, "Requests made"), h("div", { class: "code" }, r.requests.join("\n"))));
    } catch (e) { clear(results).appendChild(h("div", { class: "banner red" }, icon("alert"), e.message)); }
  };

  const section = (title, ...body) => h("div", { class: "stack" }, h("h3", null, title), body);
  const m = modal({
    title: isNew ? "New EPG template" : `Edit ${d.name}`, wide: true,
    body: h("div", { class: "stack" },
      h("div", { class: "grid-2" }, field("Name", f.name, { max: 64 }), field("Example URL", f.example_url)),
      field("Description", f.description, { max: 500 }),
      section("Request", field("How to fetch", f.fetch), dayBox),
      section("Response", h("div", { class: "small muted" }, "Dotted paths into the JSON, e.g. response.items or show.name. Use a|b to try a then b. The items path may contain day tokens, e.g. {weekday_lower}."),
        h("div", { class: "grid-2" }, field("Items path (list of shows)", f.items_path), field("Time format", f.time_format)),
        h("div", { class: "grid-3" }, field("Title", f.title), field("Description", f.description_field), field("Weekdays filter", f.days, { hint: "Comma-separated weekday names on each show" })),
        h("div", { class: "grid-3" }, field("Start", f.start), field("End", f.end), field("Duration", f.duration))),
      section("Test", h("div", { class: "row" }, testUrl, btn("Test", { icon: "play", onclick: runTest })), results)),
    foot: [isNew ? null : btn("Delete", { cls: "danger", icon: "trash", onclick: async () => {
      if (!(await confirmDialog(`Delete the template "${d.name}"?`, { danger: true, okText: "Delete" }))) return;
      try { await api("DELETE", `/api/feed-templates/${t.id}`); m.close(); route(); } catch (e) { /* toasted */ }
    } }), isNew ? null : btn("Copy JSON", { icon: "copy", onclick: () => copyText(JSON.stringify(collect(), null, 2)) }),
    h("span", { class: "spacer" }), btn("Cancel", { onclick: () => m.close() }),
    btn("Save", { cls: "primary", onclick: async () => {
      try {
        if (isNew) await api("POST", "/api/feed-templates", { definition: collect() });
        else await api("PUT", `/api/feed-templates/${t.id}`, { definition: collect() });
        toast("Template saved. Stations using it pick it up at the next refresh or Apply.", "ok"); m.close(); route();
      } catch (e) { /* toasted */ }
    } })],
  });
}

function fmtLocal(iso) {
  const d = new Date(iso);
  return isNaN(d) ? iso : d.toLocaleString(undefined, { weekday: "short", hour: "2-digit", minute: "2-digit" });
}

/* ============================== settings ============================== */

async function pageSettings(root) {
  setCrumbs("Settings");
  const s = await api("GET", "/api/settings");
  const path = inp(s.output_path, { class: "mono" });
  const writeMode = sel(s.write_mode, [["inplace", "Overwrite in place (recommended - odr-dabmux keeps the file open)"], ["atomic", "Atomic replace (write temp file + rename)"]]);
  const bitrate = bitrateSelect(s.bitrate);
  const muxName = inp(s.mux_name, { maxlength: 64, placeholder: "Defaults to the ensemble label" });
  const addr = h("input", { type: "number", min: 1, max: 1023, value: s.packet_address });
  const dg = toggle("Raw datagroup output (advanced - normally off)", s.datagroup_mode);
  const rmode = sel(s.refresh_mode, [["daily", "Once a day at a set time"], ["interval", "Every N hours"]]);
  const rtime = h("input", { type: "time", value: s.refresh_time });
  const rint = h("input", { type: "number", min: 1, max: 24, value: s.refresh_interval_hours });
  const days = h("input", { type: "number", min: 0, max: 14, value: s.epg_days });
  const tzList = h("datalist", { id: "tzlist" }, (Intl.supportedValuesOf ? Intl.supportedValuesOf("timeZone") : []).map((z) => h("option", { value: z })));
  const tz = inp(s.timezone, { list: "tzlist", placeholder: "Server default (" + Intl.DateTimeFormat().resolvedOptions().timeZone + ")" });
  const priv = toggle("Allow logo/EPG URLs on private networks (localhost, 10.x, 192.168.x …)", s.allow_private_urls);
  const sess = h("input", { type: "number", min: 1, max: 168, value: s.session_hours });
  const timeBox = field("Time", rtime), intBox = field("Interval (hours)", rint);
  const sync = () => { timeBox.classList.toggle("hidden", rmode.value !== "daily"); intBox.classList.toggle("hidden", rmode.value !== "interval"); };
  rmode.addEventListener("change", sync); sync();
  const save = async () => {
    try {
      await api("PUT", "/api/settings", { mux_name: muxName.value, output_path: path.value, write_mode: writeMode.value, bitrate: +bitrate.value, packet_address: +addr.value,
        datagroup_mode: dg.box.checked, refresh_mode: rmode.value, refresh_time: rtime.value, refresh_interval_hours: +rint.value, epg_days: +days.value,
        timezone: tz.value.trim(), allow_private_urls: priv.box.checked, session_hours: +sess.value });
      toast("Settings saved.", "ok"); refreshStatus();
      const st = await api("GET", "/api/state");
      if (st.mux_name !== S.muxName) { S.muxName = st.mux_name; setTitle(); renderShell(); }
    } catch (e) { /* toasted */ }
  };
  const card = (title, sub, ...body) => h("div", { class: "card" }, h("div", { class: "card-head" }, h("div", null, h("h2", null, title), h("p", null, sub))), h("div", { class: "card-body stack" }, body));
  put(root, h("div", { class: "page-head" }, h("div", null, h("h1", null, "Settings")), h("span", { class: "spacer" }), btn("Save settings", { cls: "primary", icon: "check", onclick: save })),
    h("div", { class: "stack" },
      card("General", "Shown on the login screen, in the browser tab and under the logo, so you can see at a glance which multiplex you're editing.",
        field("Multiplex name", muxName)),
      card("Output", "The SPI stream file read by odr-dabmux (its inputuri).",
        field("Output file", h("div", { class: "row" }, path, btn("Browse…", { icon: "folder", onclick: async () => {
          const p = await fileBrowser({ title: "Where to write the SPI stream", mode: "save", exts: "dat", start: path.value || "/home", filename: path.value.split("/").pop() || "spi-output.dat" });
          if (p) path.value = p;
        } }))), field("Write mode", writeMode)),
      h("div", { class: "grid-2" },
        card("Carousel", "Must match the SPI subchannel and component in odr-dabmux.", field("Subchannel bitrate", bitrate,
          { hint: "The packet size follows the bitrate: the largest packet that fits evenly into each 24 ms frame (Opendigitalradio's recommendation)." }), field("Packet address", addr), dg.el),
        card("Refresh schedule", "Logo URLs and EPG feeds are re-fetched and the carousel rebuilt from the last applied state. Apply always fetches too.",
          field("When", rmode), timeBox, intBox)),
      h("div", { class: "grid-2" },
        card("EPG", "Programme information sent in the carousel.", field("Days ahead", days, { hint: "0 disables EPG for all stations. Each day adds data to the carousel." }), field("Timezone", tz, { hint: "Used for schedules and the daily refresh time." }), tzList),
        card("Security", "Network access and sessions.", priv.el, h("div", { class: "small muted" }, "Leave off unless your logos are served from your own LAN - it stops users probing internal services through URL fetching."),
          field("Session length (hours)", sess))),
      updatesCard(), creditsCard()));
}

// Packet size for a bitrate: the largest DAB packet that fits a whole number of
// times into one 24 ms frame (bitrate x 3 bytes). Mirrors build.packet_size_for.
const packetSize = (kbps) => [96, 72, 48, 24].find((s) => (kbps * 3) % s === 0);

function bitrateSelect(value) {
  const opts = [];
  for (let k = 8; k <= 96; k += 8) {
    const ps = packetSize(k);
    opts.push([k, `${k} kbps · ${ps}-byte packets${ps === 24 && k > 8 ? " (less efficient)" : ""}`]);
  }
  return sel(value, opts);
}

const CREDITS = [
  ["Lucas Gallone", "Original ODR-SPI-Generator: offline SPI logo carousel generator", "https://github.com/LucasGallone/ODR-SPI-Generator"],
  ["Nick Piggott", "odr-radiodns-bridge, which the original generator was based on", "https://github.com/nickpiggott/odr-radiodns-bridge"],
  ["Opendigitalradio", "ODR-mmbTools, python-dabmot and python-dabmsc (MOT / MSC encoding)", "https://github.com/Opendigitalradio"],
  ["Ben Poor (magicbadger)", "python-hybridspi: SPI / EPG binary encoding", "https://github.com/magicbadger/python-hybridspi"],
  ["Global Radio", "python-mot-epg: EPG MOT parameters", "https://github.com/GlobalRadio/python-mot-epg"],
  ["KejPi", "AbracaDABra, used to verify SPI decoding", "https://github.com/KejPi/AbracaDABra"],
  ["Rían Mac Fhionnghaile", "MPBNL SPI WebFrontend: web UI, EPG, multi-user service", "https://github.com/ryanginn/ODR-SPI-Generator"],
];

function creditsCard() {
  return h("div", { class: "card" }, h("div", { class: "card-head" }, icon("heart"), h("div", null, h("h2", null, "Credits"),
    h("p", null, `MPBNL SPI WebFrontend ${S.version} is free software (GPLv3), built on the work of:`))),
  h("div", { class: "table-wrap" }, h("table", null, h("tbody", null, CREDITS.map(([who, what, url]) => h("tr", null,
    h("td", { class: "nowrap" }, h("b", null, who)), h("td", { class: "small" }, what),
    h("td", { class: "nowrap" }, h("a", { href: url, target: "_blank", rel: "noopener noreferrer" }, url.replace("https://", "")))))))));
}

function fmtMinSec(sec) {
  if (sec == null) return "—";
  const t = Math.round(sec), m = Math.floor(t / 60), s = t % 60;
  return m ? `${m} min ${s} s` : `${s} s`;
}

async function dismissWarning(buildId, warning) {
  try {
    await api("POST", `/api/builds/${buildId}/dismiss`, { warning });
    toast(warning === null ? "Warnings dismissed." : "Warning dismissed - it won't flag the status on future builds.", "ok");
    refreshStatus(); route();
  } catch (e) { /* toasted */ }
}

function updatesCard() {
  const body = h("div", { class: "card-body stack" }, h("span", { class: "muted" }, "Loading…"));
  const foot = h("div", { class: "card-foot" });
  const card = h("div", { class: "card" }, h("div", { class: "card-head" }, h("div", null, h("h2", null, "Updates"),
    h("p", null, "Update the generator from its git source in one click. Configuration and data are kept."))), body, foot);
  let timer = null, startCommit = null, wasRunning = false;
  const short = (c) => (c && c !== "unknown" ? c.slice(0, 7) : "unknown");
  const request = async (action) => {
    if (action === "apply" && !(await confirmDialog("Download and install the latest version now? The service restarts and this page reconnects automatically; the SPI output file is not interrupted.", { okText: "Update now" }))) return;
    try { await api("POST", "/api/update", { action }); toast(action === "apply" ? "Update started…" : "Checking for updates…"); poll(1000); } catch (e) { /* toasted */ }
  };
  const draw = (u) => {
    const st = u.status || {};
    const busy = u.pending || st.state === "running";
    if (startCommit === null) startCommit = u.current_commit;
    clear(body); clear(foot);
    foot.classList.toggle("hidden", !u.enabled);
    if (!u.enabled) {
      put(body, h("div", { class: "banner amber" }, icon("info"), "One-click updates need the generator to be installed from a git checkout with install.sh."),
        h("dl", { class: "kv" }, h("dt", null, "Version"), h("dd", null, u.version)));
      return busy;
    }
    put(body,
      h("dl", { class: "kv" },
        h("dt", null, "Installed"), h("dd", { class: "mono" }, `${u.version} · ${short(u.current_commit)}`),
        h("dt", null, "Source"), h("dd", { class: "mono small" }, `${u.source} (${u.branch})`),
        h("dt", null, "Last check"), h("dd", null, st.checked_at ? fmtAgo(st.checked_at) : "never")),
      busy ? h("div", { class: "banner blue" }, h("span", { class: "spin" }), st.message || "Starting…")
        : st.state === "error" ? h("div", { class: "banner red" }, icon("alert"), st.message)
        : st.available ? h("div", { class: "banner green" }, icon("arrowUp"), `Update available: ${short(st.remote_commit)}`)
        : st.message ? h("div", { class: "small muted" }, st.message) : null);
    put(foot, btn("Check for updates", { icon: "refresh", disabled: busy, onclick: () => request("check") }),
      btn("Update now", { cls: "primary", icon: "zap", disabled: busy, onclick: () => request("apply") }));
    return busy;
  };
  const poll = async (delay = 0) => {
    clearTimeout(timer);
    if (delay) { timer = setTimeout(() => poll(), delay); return; }
    if (!card.isConnected && startCommit !== null) return;
    let u;
    try { u = await api("GET", "/api/update", undefined, { quiet: true }); }
    catch (e) { if (wasRunning) timer = setTimeout(() => poll(), 2000); return; } // service restarting
    const busy = draw(u);
    if (wasRunning && !busy && u.current_commit !== startCommit) {
      toast(`Updated to ${short(u.current_commit)} - reloading.`, "ok");
      setTimeout(() => location.reload(), 1500);
      return;
    }
    wasRunning = busy;
    if (busy) timer = setTimeout(() => poll(), 2000);
  };
  poll();
  return card;
}

/* ============================== audit / account ============================== */

async function pageAudit(root, _parts, offset = 0) {
  setCrumbs("Audit log");
  const rows = await api("GET", `/api/audit?offset=${offset}`);
  const more = btn("Load more", { onclick: async () => {
    const next = await api("GET", `/api/audit?offset=${offset + rows.length}`);
    next.forEach((r) => tbody.appendChild(auditRow(r))); rows.push(...next);
    if (next.length < 100) more.remove();
  } });
  const tbody = h("tbody", null, rows.map(auditRow));
  put(root, h("div", { class: "page-head" }, h("div", null, h("h1", null, "Audit log"), h("p", null, "Every sign-in and change, with user and address."))),
    h("div", { class: "card" }, h("div", { class: "table-wrap" }, h("table", null, h("thead", null, h("tr", null, h("th", null, "Time"), h("th", null, "User"), h("th", null, "Address"), h("th", null, "Action"), h("th", null, "Target"), h("th", null, "Details"))), tbody)),
      rows.length >= 100 ? h("div", { class: "card-foot" }, more) : null));
}
function auditRow(r) {
  const d = Object.keys(r.details || {}).length ? JSON.stringify(r.details) : "";
  return h("tr", null, h("td", { class: "nowrap small" }, fmtDate(r.ts)), h("td", null, r.username || h("span", { class: "muted" }, "—")), h("td", { class: "mono small" }, r.ip),
    h("td", null, h("span", { class: "chip" + (r.action.includes("failed") || r.action.includes("bad") ? " red" : "") }, r.action)), h("td", { class: "small" }, r.target),
    h("td", { class: "mono small muted ellipsis", title: d }, d.length > 120 ? d.slice(0, 120) + "…" : d));
}

function pageAccount(root) {
  setCrumbs("Account");
  const dn = inp(S.user.display_name);
  const cur = h("input", { type: "password", autocomplete: "current-password" });
  const p = h("input", { type: "password", autocomplete: "new-password" });
  const p2 = h("input", { type: "password", autocomplete: "new-password" });
  put(root, h("div", { class: "page-head" }, h("div", null, h("h1", null, "Your account"), h("p", null, `${S.user.username} · ${ROLE_LABEL[S.user.role]}`))),
    h("div", { class: "grid-2" },
      h("div", { class: "card" }, h("div", { class: "card-head" }, h("h2", null, "Profile")), h("div", { class: "card-body" }, field("Display name", dn)),
        h("div", { class: "card-foot" }, btn("Save", { cls: "primary", onclick: async () => {
          try { await api("PATCH", "/api/account", { display_name: dn.value }); S.user.display_name = dn.value; toast("Saved.", "ok"); renderShell(); } catch (e) { /* toasted */ }
        } }))),
      h("div", { class: "card" }, h("div", { class: "card-head" }, h("div", null, h("h2", null, "Password"), h("p", null, "Other sessions are signed out when you change it."))),
        h("div", { class: "card-body stack" }, field("Current password", cur), field("New password", p, { hint: "At least 10 characters." }), field("Confirm new password", p2)),
        h("div", { class: "card-foot" }, btn("Change password", { cls: "primary", onclick: async () => {
          if (p.value !== p2.value) return toast("Passwords do not match.", "error");
          try { await api("POST", "/api/account/password", { current: cur.value, new: p.value }); toast("Password changed.", "ok"); cur.value = p.value = p2.value = ""; } catch (e) { /* toasted */ }
        } })))),
    h("div", { class: "section-gap" }), appearanceCard(),
    h("div", { class: "section-gap" }), h("div", { class: "small muted" }, `MPBNL SPI WebFrontend ${S.version}`));
}

function appearanceCard() {
  const seg = h("div", { class: "segmented" });
  const draw = () => {
    clear(seg);
    for (const [k, label, ic] of THEMES) {
      seg.appendChild(h("button", { type: "button", class: getTheme() === k ? "on" : "", onclick: () => { setTheme(k); draw(); renderShell(); } },
        h("span", { class: "row" }, icon(ic), label)));
    }
  };
  draw();
  return h("div", { class: "card" }, h("div", { class: "card-head" }, h("div", null, h("h2", null, "Appearance"),
    h("p", null, "Saved in this browser. System follows your device's light/dark setting."))), h("div", { class: "card-body" }, seg));
}

boot();
