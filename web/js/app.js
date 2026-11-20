
"use strict";
const $ = (id) => document.getElementById(id);
const api = () => window.pywebview.api;

const state = {
  format: "mp3", quality: "320",
  proxy_enabled: false, proxy_type: "http", proxy_url: "",
  folder: "", youtube_po_token: "", busy: false, ready: false, signin: null, cookies: {},
  itemTotal: 0, itemDone: 0, streams: 1, stream: 0, title: "",
  source: "spotify",
  yt: { kind: "video", quality: "best" },
  tt: { quality: "best" },
  x: { quality: "best" },
  general: { kind: "video", quality: "best" },
  docs: { kind: "document" },
};

/* ------------------------------------------------------------- chrome --- */
const PAGES = [
  ["download", "Spotify"],
  ["youtube", "YouTube"],
  ["ytmusic", "YouTube Music"],
  ["tiktok", "TikTok"],
  ["instagram", "Instagram"],
  ["soundcloud", "SoundCloud"],
  ["x", "X"],
  ["general", "Video"],
  ["pdf", "Documents & Ebooks"],
  ["connection", "Connection"],
  ["settings", "Downloader settings"],
];
const SECTION_ICONS = {
  download: '<path d="M5 9.2c4.8-1.4 9.8-.9 13.8 1.3M6 12.8c4-1.1 8.2-.7 11.6 1.1M7 16.1c3-.7 6.1-.4 8.8.8"/>',
  youtube: '<rect x="3" y="6" width="18" height="12" rx="4"/><path d="m10 9 5 3-5 3Z" fill="var(--pane-solid)" stroke="none"/>',
  ytmusic: '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="5.2"/><path d="m10.5 9 4.8 3-4.8 3Z" fill="currentColor" stroke="none"/>',
  tiktok: '<path d="M14 4v9.2a4 4 0 1 1-3-3.9M14 4c.5 2.2 1.8 3.6 4 4"/>',
  instagram: '<rect x="4" y="4" width="16" height="16" rx="5"/><circle cx="12" cy="12" r="3.6"/><circle cx="17.4" cy="6.8" r=".8" fill="currentColor" stroke="none"/>',
  soundcloud: '<path d="M9 16H6.8a2.8 2.8 0 1 1 1.1-5.4A5.2 5.2 0 0 1 18 12a2.2 2.2 0 1 1 0 4h-2M6 13v3M9 10v6M12 8v8M15 10v6"/>',
  x: '<path d="M5 4.5 18.8 19.5M18.5 4.5 5.2 19.5"/>',
  general: '<rect x="3" y="5" width="18" height="14" rx="3"/><path d="m10 9 5 3-5 3Z"/>',
  pdf: '<path d="M7 3.5h7l4 4V20H7zM14 3.5V8h4M9.5 12h6M9.5 15h6"/>',
  telegram: '<path d="M21.5 4.6 2.9 11.9a.4.4 0 0 0 .03.75l4.6 1.45 1.75 5.2a.4.4 0 0 0 .7.14l2.45-2.75 4.5 3.3a.4.4 0 0 0 .63-.23Z"/><path d="M21.5 4.6 7.53 14.1l2.45 5.34 2.45-2.75"/>',
  connection: '<circle cx="6" cy="12" r="2.5"/><circle cx="18" cy="6" r="2.5"/><circle cx="18" cy="18" r="2.5"/><path d="m8.3 10.8 7.4-3.6M8.3 13.2l7.4 3.6"/>',
  settings: '<path d="M4 7h7M15 7h5M4 12h3M11 12h9M4 17h9M17 17h3"/><circle cx="13" cy="7" r="2"/><circle cx="9" cy="12" r="2"/><circle cx="15" cy="17" r="2"/>',
};
function sectionSvg(id) {
  const paths = SECTION_ICONS[id] || SECTION_ICONS.general;
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${paths}</svg>`;
}
function sectionIcon(id) {
  return `<span class="section-icon" aria-hidden="true">${sectionSvg(id)}</span>`;
}
/* Only the source pages retint. Settings pages keep whichever source is active,
   so opening settings never looks like you left the source you were using. */
const MODES = {
  download: "spotify", youtube: "youtube", ytmusic: "ytmusic", tiktok: "tiktok",
  instagram: "instagram", soundcloud: "soundcloud", x: "x",
  general: "general", pdf: "pdf",
};
const LABELS = {
  spotify: "Spotify", youtube: "YouTube", ytmusic: "YouTube Music", tiktok: "TikTok",
  instagram: "Instagram", soundcloud: "SoundCloud", x: "X",
  general: "Video", pdf: "Documents & Ebooks",
};
const UTILITY_TINTS = { connection: "var(--knight-2)", settings: "var(--amber)" };
function sectionTint(id) {
  return MODES[id] ? `var(--src-${MODES[id]})` : (UTILITY_TINTS[id] || "var(--knight-2)");
}

function decoratePages() {
  document.querySelectorAll(".page[data-page]").forEach(page => {
    const id = page.dataset.page;
    page.style.setProperty("--section-tint", sectionTint(id));
    const head = page.querySelector(".page-head");
    if (head && !head.querySelector(".section-icon")) {
      head.insertAdjacentHTML("afterbegin", sectionIcon(id));
    }
  });
}

function buildNav() {
  const nav = $("nav");
  const androidLayout = document.documentElement.classList.contains("android");
  PAGES.forEach(([id, label], i) => {
    const b = document.createElement("button");
    b.className = i === 0 ? "on" : "";
    b.dataset.target = id;
    b.style.setProperty("--section-tint", sectionTint(id));
    b.innerHTML = '<span class="dot"></span>' +
      ((PHONE.matches || androidLayout) ? sectionIcon(id) : "");
    b.appendChild(document.createTextNode(label));
    b.onclick = () => show(id);
    nav.appendChild(b);
  });
  if (PHONE.matches || androidLayout) {
    decoratePages();
    $("mbar-icon").style.setProperty("--section-tint", sectionTint("download"));
    $("mbar-icon").innerHTML = sectionSvg("download");
  }
}

/* ------------------------------------------------------------ phone shell ---
   The desktop window cannot be narrow enough to reach any of this: its minimum
   is 1005px. Everything here is the Android build's navigation.

   The tiles are built from the same PAGES and MODES the sidebar uses, so a
   source added in one place appears in both. The sidebar's utility buttons are
   moved into the sheet rather than copied, which keeps their ids unique and
   their existing wiring intact. */
const PHONE = matchMedia("(max-width: 760px)");

function sheetTile(id, label, tint, extra) {
  const tile = document.createElement("button");
  tile.className = "tile" + (extra || "");
  tile.dataset.target = id;
  tile.style.setProperty("--tint", tint);
  tile.insertAdjacentHTML("afterbegin", sectionIcon(id));
  const name = document.createElement("b");
  name.textContent = label;
  tile.appendChild(name);
  return tile;
}

function buildSheet() {
  const grid = $("sheet-grid");
  PAGES.forEach(([id, label]) => {
    const tile = sheetTile(id, label, sectionTint(id), MODES[id] ? "" : " utility");
    tile.onclick = () => { show(id); closeSheet(); };
    grid.appendChild(tile);
  });
  // The channel is one of the places this app takes you, so it belongs among
  // the others rather than as a button parked under them.
  const chat = sheetTile("telegram", "Telegram channel", "var(--src-telegram)",
                         " utility");
  chat.onclick = () => { closeSheet(); api().open_telegram(); };
  grid.appendChild(chat);
  const foot = document.querySelector(".side-foot");
  if (foot) $("sheet-foot").appendChild(foot);
}

function syncPhoneProgress() {
  const progress = $("phone-progress");
  const main = $("main");
  const runbar = $("runbar");
  const activity = runbar.querySelector(".console-head");
  const parts = [
    document.querySelector(".status-block"),
    // The card travels with the progress it describes. Left behind, it ends up
    // beside the activity log while the bar it belongs to is at the top.
    document.getElementById("preview"),
    runbar.querySelector(".bar") || progress.querySelector(".bar"),
    $("run-path"),
    document.querySelector(".run-stats"),
  ].filter(Boolean);
  // Re-parenting a node that is already in place still detaches and reinserts
  // it, and this runs on every page switch — which on a phone is every tap on
  // a source tile. The moves are skipped only when the whole run is already
  // sitting in order, because a half-checked reorder is worse than none.
  const inOrderUnder = (parent, before) => parts.every((part, i) =>
    part.parentNode === parent &&
    part.nextElementSibling === (parts[i + 1] || before));

  if (PHONE.matches) {
    const actions = document.querySelector(".page.on .paste-row");
    if (!inOrderUnder(progress, null)) {
      parts.forEach(part => progress.appendChild(part));
    }
    if (actions && actions.nextElementSibling !== progress) {
      actions.insertAdjacentElement("afterend", progress);
    }
  } else {
    if (!inOrderUnder(runbar, activity)) {
      parts.forEach(part => runbar.insertBefore(part, activity));
    }
    const firstPage = main.querySelector(".page");
    if (progress.nextElementSibling !== firstPage) main.insertBefore(progress, firstPage);
  }
}

/* The sheet used to vanish on the frame it was dismissed, which is what made
   it feel like a menu rather than a surface. It now leaves the same way it
   arrived, so the close is held open long enough for the exit to play. */
let sheetExit = null;

function openSheet() {
  const current = document.querySelector(".page.on")?.dataset.page;
  // Only the tiles whose answer changed. Rewriting all twelve invalidated all
  // twelve, and the current-tile rule is the most expensive style on the page
  // — so every open was recalculating eleven tiles to tell them nothing.
  document.querySelectorAll("#sheet-grid .tile").forEach(t => {
    const now = String(t.dataset.target === current);
    if (t.getAttribute("aria-current") !== now) t.setAttribute("aria-current", now);
  });
  clearTimeout(sheetExit);
  $("sheet").classList.remove("closing");
  $("sheet").hidden = false;
  $("mbar-source").setAttribute("aria-expanded", "true");
}

function closeSheet() {
  const sheet = $("sheet");
  $("mbar-source").setAttribute("aria-expanded", "false");
  if (sheet.hidden) return;
  clearTimeout(sheetExit);
  sheet.classList.add("closing");
  sheetExit = setTimeout(() => {
    sheet.hidden = true;
    sheet.classList.remove("closing");
  }, 190);
}

function setupPhone() {
  syncPhoneProgress();
  const foot = document.querySelector(".side-foot");
  const theme = $("theme-btn");
  if (!PHONE.matches) {
    if (foot) document.querySelector(".side").appendChild(foot);
    // Last child of the sidebar footer is where it started.
    if (foot && theme) foot.appendChild(theme);
    return;
  }
  // Theme is a property of the app, not of the section you are picking, so on
  // a phone it lives in the bar and is deliberately kept out of the sheet the
  // rest of .side-foot moves into.
  $("mbar").insertBefore(theme, $("mbar-more"));
  if (!setupPhone.done) {
    setupPhone.done = true;
    buildSheet();
    decoratePages();
    $("mbar-icon").style.setProperty("--section-tint", sectionTint("download"));
    $("mbar-icon").innerHTML = sectionSvg("download");
    // Open on the picker. A downloader's first question is which source, and
    // answering it with a tap beats landing on one of eleven pages and having
    // to find the way to the other ten. Back closes it onto Spotify, which is
    // where the app used to start.
    openSheet();
  } else if (foot) {
    $("sheet-foot").appendChild(foot);
  }
  $("mbar-source").onclick = openSheet;
  $("sheet-scrim").onclick = closeSheet;
  $("sheet-close").onclick = closeSheet;
  // Both open the picker. Settings and Connection are tiles inside it, so
  // nothing became unreachable — the button that used to go straight to one
  // page now goes to all of them.
  $("mbar-more").onclick = openSheet;
}
if (PHONE.addEventListener) PHONE.addEventListener("change", setupPhone);
else PHONE.addListener(setupPhone);

/* What Back means inside the app, answered by the page because the page is
   what knows. Returns true when it did something, so the shell can tell the
   difference between "handled" and "there is nothing left, close the app".

   The order is what a person would expect to undo: the sheet if it is open,
   then a source that is not the one the app starts on, then nothing. */
window.blueknightBack = function () {
  if (!$("sheet").hidden) {
    closeSheet();
    return true;
  }
  const current = document.querySelector(".page.on")?.dataset.page;
  if (current && current !== PAGES[0][0]) {
    show(PAGES[0][0]);
    return true;
  }
  return false;
};

/* A link shared into the app from anywhere else lands in the open source's
   field, ready to download — the shell calls this. */
/* Which source a link belongs to. The same domains the engine matches on, in
   the order that resolves the overlaps: music.youtube.com is YouTube Music
   rather than YouTube, and both are checked before the catch-all. */
const LINK_SOURCES = [
  ["ytmusic",    /^https?:\/\/music\.youtube\.com\//i],
  ["download",   /^https?:\/\/(?:[\w-]+\.)*(?:open\.)?spotify\.com\//i],
  ["youtube",    /^https?:\/\/(?:[\w-]+\.)*(?:youtube\.com|youtu\.be)\//i],
  ["tiktok",     /^https?:\/\/(?:[\w-]+\.)*tiktok\.com\//i],
  ["instagram",  /^https?:\/\/(?:[\w-]+\.)*instagram\.com\//i],
  ["soundcloud", /^https?:\/\/(?:[\w-]+\.)*soundcloud\.com\//i],
  ["x",          /^https?:\/\/(?:[\w-]+\.)*(?:x\.com|twitter\.com)\//i],
];

/* The card: what is coming down, while it comes down.

   The artwork is only ever YouTube's, and only because it costs nothing —
   the thumbnail address is derivable from the video id, so there is no extra
   request to work out what to show. Every other source keeps the tinted panel,
   which is honest: the app does not know the picture and will not fetch one to
   find out. */
function showPreview(title, sub, url) {
  const card = $("preview");
  if (!card) return;
  if (!title) { card.hidden = true; return; }
  $("preview-title").textContent = title;
  $("preview-sub").textContent = sub || "";
  const art = $("preview-art");
  const id = /(?:v=|youtu\.be\/|\/shorts\/|\/embed\/)([A-Za-z0-9_-]{11})/.exec(url || "");
  art.style.backgroundImage =
    id ? `url("https://i.ytimg.com/vi/${id[1]}/mqdefault.jpg")` : "";
  card.hidden = false;
}

function hidePreview() {
  const card = $("preview");
  if (card) { card.hidden = true; $("preview-art").style.backgroundImage = ""; }
}

function sourceForLink(url) {
  const text = String(url || "").trim();
  for (const [page, pattern] of LINK_SOURCES) {
    if (pattern.test(text)) return page;
  }
  return /^https?:\/\//i.test(text) ? "general" : null;
}

/* Put a link where it belongs, whichever page is open.

   Pasting a TikTok link into the Spotify box was a thing a person could do and
   then be told the link was wrong, when the app knew perfectly well what it
   was. The page follows the link instead. */
function routeLink(url, { focus = false } = {}) {
  const page = sourceForLink(url);
  if (!page) return false;
  if (document.querySelector(".page.on")?.dataset.page !== page) {
    closeSheet();
    show(page);
  }
  const field = document.querySelector(".page.on .paste-row input");
  if (!field) return false;
  field.value = url;
  field.dispatchEvent(new Event("input", { bubbles: true }));
  if (focus) field.focus();
  return true;
}

window.blueknightShared = function (url) {
  routeLink(url, { focus: true });
};

function show(id) {
  document.querySelectorAll(".page").forEach(p => p.classList.toggle("on", p.dataset.page === id));
  document.querySelectorAll("#nav button").forEach(b => b.classList.toggle("on", b.dataset.target === id));
  const label = (PAGES.find(([page]) => page === id) || [, ""])[1];
  if ($("mbar-label") && label) $("mbar-label").textContent = label;
  if ($("mbar-icon")) {
    $("mbar-icon").style.setProperty("--section-tint", sectionTint(id));
    $("mbar-icon").innerHTML = sectionSvg(id);
  }
  $("main").dataset.runbar = MODES[id] ? "on" : "off";
  if (PHONE.matches) syncPhoneProgress();
  // A finished job belongs to the page it ran on, not the one being opened.
  if (!state.busy) resetRun();
  if (MODES[id] && !state.busy) {
    state.source = MODES[id];
    document.documentElement.dataset.mode = state.source;
    refreshStats();
  }
}

/* One button per source, and it says which of the three states it is in:
   nothing stored, a live session, or a login window waiting to be finished. */
function paintSignin() {
  document.querySelectorAll("[data-signin]").forEach(b => {
    const kind = b.dataset.signin;
    const site = kind[0].toUpperCase() + kind.slice(1);
    const active = state.signin === kind;
    const saved = (state.cookies || {})[kind];
    b.textContent = active ? "Finish sign-in"
                  : saved && saved.signed_in ? "Signed in · sign in again"
                  : "Sign in to " + site;
    b.classList.toggle("primary", active);
    // While one login window is open, the others would only collide with it.
    b.disabled = Boolean(state.signin) && !active;
    const note = b.parentElement.querySelector(".signin-note");
    if (note) note.textContent = saved && saved.signed_in ? "âœ“ " + saved.detail : "";
  });
}

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  // The button is named for what it does, not for what is currently on — and
  // in the app bar it is icon-only, so the name has to survive as a label.
  const going = theme === "dark" ? "light" : "dark";
  $("theme-label").textContent = going === "light" ? "Light theme" : "Dark theme";
  $("theme-btn").setAttribute("aria-label", `Switch to ${going} theme`);
  $("theme-btn").title = `Switch to ${going} theme`;
}

const AUDIO_CONVERTER_FORMATS = new Set(["mp3", "flac", "wav", "m4a", "ogg", "aac"]);

function paintConverter() {
  const format = $("media-convert-format").value;
  const audioOnly = AUDIO_CONVERTER_FORMATS.has(format);
  const mode = audioOnly ? "audio" : "video";
  document.querySelectorAll("[data-converter-mode]").forEach(button => {
    button.setAttribute("aria-pressed", String(button.dataset.converterMode === mode));
  });
  document.querySelectorAll("[data-converter-panel]").forEach(panel => {
    panel.hidden = panel.dataset.converterPanel !== mode;
  });
  document.querySelectorAll(".format-picker [data-format]").forEach(button => {
    button.setAttribute("aria-checked", String(button.dataset.format === format));
  });
  const lossless = ["flac", "wav"].includes(format);
  $("media-custom-size").hidden = $("media-convert-resize").value !== "custom";
  $("audio-bitrate-control").hidden = lossless;
  const codec = $("media-convert-codec");
  codec.disabled = format === "webm" || format === "avi";
  $("media-convert-upscale").disabled = $("media-convert-resize").value === "source";
  $("media-convert-frame-mode").disabled = $("media-convert-fps").value === "source";
  if (format === "webm") codec.value = "vp9";
  if (format === "avi") codec.value = "h264";
  $("convert-media").textContent = audioOnly
    ? "Choose audio or video & convert audio" : "Choose video & convert";
}

function converterOptions() {
  const audioOnly = AUDIO_CONVERTER_FORMATS.has($("media-convert-format").value);
  return {
    format: $("media-convert-format").value,
    codec: $("media-convert-codec").value,
    quality: $("media-convert-quality").value,
    resize: $("media-convert-resize").value,
    fps: $("media-convert-fps").value,
    frame_mode: $("media-convert-frame-mode").value,
    upscale: $("media-convert-upscale").value,
    video_enhance: $("media-convert-video-enhance").value,
    audio_enhance: audioOnly ? $("audio-convert-enhance").value
                             : $("video-convert-audio-enhance").value,
    audio_bitrate: audioOnly ? $("audio-convert-bitrate").value
                             : $("video-convert-bitrate").value,
    width: Number($("media-convert-width").value) || 0,
    height: Number($("media-convert-height").value) || 0,
  };
}

/* -------------------------------------------------------------- toasts -- */
function toast(message, kind = "info", ms = 5200) {
  const el = document.createElement("div");
  el.className = "toast " + kind;
  el.textContent = message;
  $("toasts").appendChild(el);
  setTimeout(() => el.remove(), ms);
}

/* ------------------------------------------------------------- console -- */
/* One batch, one layout. Written per line this read scroll geometry, appended,
   then wrote scroll position — forcing a synchronous layout for every line in
   a burst, which is exactly when a download is busiest. */
function logLines(lines) {
  if (!lines.length) return;
  const c = $("console");
  const near = c.scrollHeight - c.scrollTop - c.clientHeight < 40;
  const stamp = new Date().toTimeString().slice(0, 8) + "  ";
  const batch = document.createDocumentFragment();
  lines.forEach(([message, level]) => {
    const line = document.createElement("div");
    line.className = level || "info";
    line.textContent = stamp + message;
    batch.appendChild(line);
  });
  c.appendChild(batch);
  while (c.childElementCount > 800) c.removeChild(c.firstChild);
  if (near) c.scrollTop = c.scrollHeight;
}
function logLine(message, level) { logLines([[message, level]]); }

/* ------------------------------------------------------------ segments -- */
function segment(id, onPick) {
  $(id).querySelectorAll("button").forEach(b => {
    b.onclick = () => {
      $(id).querySelectorAll("button").forEach(o => o.setAttribute("aria-pressed", String(o === b)));
      onPick(b.dataset.value);
    };
  });
}
function setSegment(id, value) {
  $(id).querySelectorAll("button").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.value === value)));
}

const GO_BUTTONS = ["download", "yt-go", "ym-go", "tt-go", "ig-go", "sc-go", "x-go",
                    "gen-go", "pdf-go"];
const STOP_BUTTONS = ["stop", "yt-stop", "ym-stop", "tt-stop", "ig-stop", "sc-stop", "x-stop",
                      "gen-stop", "pdf-stop"];

function setBusy(busy) {
  state.busy = busy;
  document.body.classList.toggle("busy", busy);
  $("eq-label").textContent = busy ? "Downloading" : "Idle";
  GO_BUTTONS.forEach(id => { $(id).disabled = busy || !state.ready; });
  STOP_BUTTONS.forEach(id => { $(id).disabled = !busy; });
}

/* Put the run bar back to idle. Called when a finished job has been on screen
   long enough, and whenever the page changes, so no source inherits another's
   result. Never while something is running. */
function resetRun() {
  clearTimeout(resetRun.timer);
  if (state.busy) return;
  state.itemTotal = 0; state.itemDone = 0;
  state.streams = 1; state.stream = 0; state.title = "";
  setProgress(0);
  $("status-word").textContent = "Ready";
  $("status-meta").textContent = "nothing downloading";
  hidePreview();
  $("stat-count").textContent = "—";
  $("run-path").textContent = "";
}

/* Where the whole job stands, given a percentage for the file in flight.
   A playlist of 40 songs is not 100% done because song 1 finished, and a video
   is not finished because its video stream is — the audio is still to come. */
function jobPercent(filePct) {
  const items = Math.max(1, state.itemTotal || 1);
  const streams = Math.max(1, state.streams || 1);
  const withinItem = (Math.min(state.stream, streams - 1) + filePct / 100) / streams;
  return Math.min(100, ((state.itemDone + withinItem) / items) * 100);
}

function setProgress(pct, kind) {
  const fill = $("bar-fill");
  fill.style.width = Math.max(0, Math.min(100, pct)) + "%";
  fill.className = "bar-fill" + (kind ? " " + kind : "");
  $("stat-pct").textContent = Math.round(pct) + "%";
}

function refreshStats() {
  const mp3 = state.format === "mp3";
  const audioFormat = state.format === "flac" ? "FLAC" : "MP3 " + state.quality;
  $("stat-source").textContent = LABELS[state.source];
  $("stat-format").textContent =
    state.source === "spotify"
      ? (mp3 ? "MP3 " + state.quality : state.format.toUpperCase())
      : state.source === "youtube" && state.yt.kind === "audio"
        ? audioFormat
      // YouTube Music is audio, always — there is no video to choose.
      : state.source === "soundcloud" || state.source === "ytmusic"
        || (state.source === "general" && state.general.kind === "audio")
        ? audioFormat
        // Instagram has no quality ladder: you get what was posted. Documents
        // have no format ladder at all — a PDF is a PDF.
        : { youtube: state.yt.quality, tiktok: state.tt.quality, instagram: "source",
            x: state.x.quality, pdf: state.docs.kind === "manga" ? "PDF + CBZ" : "source",
            general: state.general.quality }[state.source].toUpperCase();
  $("yt-quality-field").classList.toggle("muted", state.yt.kind === "audio");
  $("gen-quality-field").classList.toggle("muted", state.general.kind === "audio");
  $("stat-proxy").textContent = state.proxy_enabled ? state.proxy_type.toUpperCase() : "off";

  // Only offer what currently applies.
  $("quality-field").classList.toggle("muted", !mp3);
  $("format-note").textContent = mp3
    ? "320 kbps is the highest MP3 quality Spotify sources support."
    : state.format === "flac"
      ? "FLAC is lossless from the source file. Bitrate does not apply."
      : "Best available keeps the source format, whatever it is.";
  $("proxy-type-field").classList.toggle("muted", !state.proxy_enabled);
  $("proxy-url-field").classList.toggle("muted", !state.proxy_enabled);
}

function setReady(ready) {
  state.ready = ready;
  GO_BUTTONS.forEach(id => {
    $(id).disabled = !ready || state.busy;
    $(id).textContent = ready ? "Download" : "Setting up…";
  });
}

/* ---------------------------------------------------------- event pump -- */
function handle(ev) {
  const [action, args] = ev;
  switch (action) {
    case "log":
      logLines(args);
      break;
    case "status":
      $("status-word").textContent = args[0];
      break;
    case "plan":
      // What this job consists of, before any of it happens.
      state.itemTotal = args[0] || 1;
      state.streams = args[1] || 1;
      state.itemDone = 0;
      state.stream = 0;
      // A single item is on its way as soon as the job starts; a playlist is not.
      $("stat-count").textContent = (state.itemTotal === 1 ? "1 / 1"
                                                          : "0 / " + state.itemTotal);
      $("run-path").textContent = args[2] || "";
      break;
    case "track": {
      const [count, total, name] = args;
      state.itemDone = Math.max(0, count - 1);
      state.itemTotal = total || state.itemTotal;
      state.stream = 0;
      if (name) {
        $("status-meta").textContent = name;
        showPreview(name, state.itemTotal > 1
          ? `${count} of ${state.itemTotal} · ${LABELS[state.source] || ""}`
          : (LABELS[state.source] || ""), state.lastUrl);
      }
      $("stat-count").textContent = state.itemTotal
        ? count + " / " + state.itemTotal : String(count);
      setProgress(jobPercent(0));
      break;
    }
    case "total":
      state.itemTotal = args[0];
      $("stat-count").textContent = state.itemDone + " / " + args[0];
      break;
    case "file":
      // Each destination is one more stream of the current item finished.
      state.stream = Math.max(0, (args[1] || 1) - 1);
      $("run-path").textContent = args[0] || $("run-path").textContent;
      break;
    case "stage":
      $("status-meta").textContent = args[0];
      break;
    case "bytes": {
      // yt-dlp counts bytes per file, so the raw number hits 100% once per
      // stream. Fold it into the whole job before showing it.
      const [pct, title, speed, eta] = args;
      if (title) state.title = title;
      // yt-dlp says "NA"/"Unknown" when it cannot estimate; neither is worth showing.
      const known = v => v && !["NA", "Unknown", "N/A", "--:--"].includes(v);
      const detail = [known(speed) ? speed : "", known(eta) ? "ETA " + eta : ""]
        .filter(Boolean).join(" · ");
      $("status-meta").textContent = detail
        ? (state.title ? state.title + " — " + detail : detail)
        : (state.title || "downloading…");
      setProgress(jobPercent(pct));
      break;
    }
    case "success":
      setProgress(100, "done");
      if (state.itemTotal)
        $("stat-count").textContent = state.itemTotal + " / " + state.itemTotal;
      $("status-word").textContent = "Done";
      $("status-meta").textContent = "finished in " + args[0].toFixed(1) + "s";
      toast("Download complete.", "ok");
      break;
    case "failure":
      setProgress(100, "failed");
      $("status-word").textContent = "Failed";
      toast(args[0], "err", 12000);
      break;
    case "finished":
      setBusy(false);
      if ($("status-word").textContent === "Downloading") $("status-word").textContent = "Ready";
      $("status-meta").textContent = "nothing downloading";
      // Leave the result up long enough to read, then clear it: a full green bar
      // is about the job that ended, and it has no business greeting the next one.
      clearTimeout(resetRun.timer);
      resetRun.timer = setTimeout(resetRun, 6000);
      break;
    case "setup":
      $("gate-title").textContent = args[0];
      $("gate-detail").textContent = args[1];
      break;
    case "setup_done":
      $("gate").hidden = true;
      $("status-word").textContent = "Ready";
      setReady(true);
      break;
    case "setup_error":
      $("gate").hidden = true;
      $("status-word").textContent = "Setup failed";
      setReady(true);
      toast(args[0] + "\n\n" + args[1] + "\n\nSet a proxy in Connection settings, then run Check setup.", "err", 20000);
      break;
    case "updating": {
      const busy = args[0];
      $("update-btn").disabled = busy;
      $("update-components").disabled = busy;
      $("update-label").textContent = busy ? "Updating all components…" : "Update all components";
      break;
    }
    case "converting": {
      const busy = args[0];
      $("convert-media").disabled = busy;
      $("convert-document").disabled = busy;
      $("convert-image-folder").disabled = busy;
      document.querySelectorAll(".converter-input").forEach(el => { el.disabled = busy; });
      document.querySelectorAll(".format-picker button, [data-converter-mode]").forEach(el => { el.disabled = busy; });
      $("converter-status").textContent = busy
        ? (args[1] === "document" ? "Converting document..."
          : args[1] === "images" ? "Merging ordered images..." : "Converting media...")
        : "Ready";
      if (!busy) paintConverter();
      break;
    }
    case "components":
      $("components").textContent = args[0];
      break;
    case "folder":
      $("folder").value = args[0];
      state.folder = args[0];
      break;
    case "signin":
      state.signin = args[0];
      paintSignin();
      break;
    case "cookie_status":
      state.cookies = args[0] || {};
      paintSignin();
      break;
    case "proxy":
      state.proxy_type = args[0];
      state.proxy_url = args[1];
      state.proxy_enabled = args[2];
      setSegment("proxy-type", args[0]);
      $("proxy-url").value = args[1];
      $("proxy-toggle").setAttribute("aria-checked", String(args[2]));
      refreshStats();
      break;
    case "toast":
      toast(args[0], args[1] || "info", args[1] === "err" ? 12000 : 5200);
      break;
  }
}

/* On the desktop the engine is a separate process and an empty poll costs
   almost nothing. On Android the page, the engine and the download itself
   share one interpreter, so every poll takes the GIL away from the download
   just to be told nothing happened. Answering quickly while events are
   arriving and easing off when they are not keeps the progress bar as live as
   it was, on a fraction of the round trips. */
async function pump() {
  let events = [];
  try {
    events = (await api().poll()) || [];
    events.forEach(handle);
  } catch (e) { /* bridge not up yet */ }
  pump.quiet = events.length ? 0 : Math.min((pump.quiet || 0) + 1, 8);
  setTimeout(pump, state.busy ? 120 + pump.quiet * 40 : 350);
}

/* --------------------------------------------------------------- wiring -- */
function wire() {
  $("w-min").onclick = () => api().minimize();
  $("w-max").onclick = () => api().toggle_maximize();
  $("w-close").onclick = () => api().close();
  $("theme-btn").onclick = () =>
    applyTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark");
  $("telegram-btn").onclick = () => api().open_telegram();

  $("download").onclick = () => {
    const url = $("url").value.trim();
    if (!url) { toast("Paste a Spotify link first.", "err"); return; }
    setBusy(true);
    setProgress(0);
    state.itemTotal = 0; state.itemDone = 0; state.stream = 0;
    state.title = "";
    $("status-word").textContent = "Downloading";
    $("status-meta").textContent = "starting…";
    api().start_download(url, state.format, state.quality);
  };
  $("url").addEventListener("keydown", e => { if (e.key === "Enter") $("download").click(); });
  STOP_BUTTONS.forEach(id => { $(id).onclick = () => api().stop_download(); });

  // One paste handler for every source: the button names its target field.
  document.querySelectorAll("[data-paste]").forEach(b => {
    b.onclick = async () => {
      const text = await api().clipboard();
      if (!text) { toast("Clipboard has no link.", "err"); return; }
      // A link knows which page it belongs to, so pasting a TikTok link into
      // the Spotify box moves to TikTok rather than reporting a bad link.
      const moved = sourceForLink(text);
      if (moved && moved !== document.querySelector(".page.on")?.dataset.page) {
        routeLink(text);
        toast(`That is a ${(PAGES.find(([p]) => p === moved) || [, moved])[1]} link.`, "ok");
      } else {
        $(b.dataset.paste).value = text;
      }
    };
  });

  // Typing or dropping a link in also follows it, once the link looks whole.
  document.querySelectorAll(".paste-row input").forEach(field => {
    field.addEventListener("paste", event => {
      const text = (event.clipboardData || window.clipboardData)?.getData("text");
      const moved = sourceForLink(text);
      if (!moved || moved === document.querySelector(".page.on")?.dataset.page) return;
      event.preventDefault();
      routeLink(text.trim());
      toast(`That is a ${(PAGES.find(([p]) => p === moved) || [, moved])[1]} link.`, "ok");
    });
  });

  const startMedia = (kind, urlId, limitId, quality, audio) => {
    const url = $(urlId).value.trim();
    if (!url) { toast("Paste a link first.", "err"); return; }
    setBusy(true);
    setProgress(0);
    state.itemTotal = 0; state.itemDone = 0; state.stream = 0;
    state.title = "";
    // Kept so the card can show the thumbnail before the engine has said what
    // the title is — the link is the only thing known at this point.
    state.lastUrl = url;
    showPreview("Fetching details…", LABELS[state.source] || "", url);
    $("status-word").textContent = "Downloading";
    $("status-meta").textContent = "reading the link…";
    const limit = limitId ? parseInt($(limitId).value.trim(), 10) : NaN;
    api().start_media(kind, url, quality, audio, Number.isFinite(limit) ? limit : 0);
  };

  $("yt-go").onclick = () =>
    startMedia("youtube", "yt-url", "yt-limit", state.yt.quality, state.yt.kind === "audio");
  $("tt-go").onclick = () => startMedia("tiktok", "tt-url", "tt-limit", state.tt.quality, false);
  $("ig-go").onclick = () => startMedia("instagram", "ig-url", "ig-limit", "best", false);
  $("sc-go").onclick = () => startMedia("soundcloud", "sc-url", "sc-limit", "best", true);
  $("x-go").onclick = () => startMedia("x", "x-url", null, state.x.quality, false);
  $("ym-go").onclick = () => startMedia("ytmusic", "ym-url", "ym-limit", "best", true);
  $("gen-go").onclick = () =>
    startMedia("general", "gen-url", "gen-limit", state.general.quality,
               state.general.kind === "audio");
  $("pdf-go").onclick = () => {
    const url = $("pdf-url").value.trim();
    if (!url) { toast("Paste a link first.", "err"); return; }
    setBusy(true);
    setProgress(0);
    state.itemTotal = 0; state.itemDone = 0; state.stream = 0;
    state.title = "";
    $("status-word").textContent = "Downloading";
    $("status-meta").textContent = state.docs.kind === "manga" ? "reading the chapter…" : "reading the page…";
    const limit = parseInt($("pdf-limit").value.trim(), 10);
    if (state.docs.kind === "manga") api().start_manga(url, Number.isFinite(limit) ? limit : 0);
    else api().start_pdf(url, Number.isFinite(limit) ? limit : 0);
  };

  $("yt-url").addEventListener("keydown", e => { if (e.key === "Enter") $("yt-go").click(); });
  $("tt-url").addEventListener("keydown", e => { if (e.key === "Enter") $("tt-go").click(); });
  $("ig-url").addEventListener("keydown", e => { if (e.key === "Enter") $("ig-go").click(); });
  $("sc-url").addEventListener("keydown", e => { if (e.key === "Enter") $("sc-go").click(); });
  $("x-url").addEventListener("keydown", e => { if (e.key === "Enter") $("x-go").click(); });
  $("gen-url").addEventListener("keydown", e => { if (e.key === "Enter") $("gen-go").click(); });
  $("ym-url").addEventListener("keydown", e => { if (e.key === "Enter") $("ym-go").click(); });
  $("pdf-url").addEventListener("keydown", e => { if (e.key === "Enter") $("pdf-go").click(); });

  // One button per source: it opens the login window, then finishes the job.
  document.querySelectorAll("[data-signin]").forEach(b => {
    b.onclick = () => {
      if (state.signin === b.dataset.signin) { api().finish_sign_in(); }
      else { api().sign_in(b.dataset.signin); }
    };
  });

  segment("yt-kind", v => { state.yt.kind = v; refreshStats(); });
  segment("yt-quality", v => { state.yt.quality = v; refreshStats(); });
  segment("tt-quality", v => { state.tt.quality = v; refreshStats(); });
  segment("x-quality", v => { state.x.quality = v; refreshStats(); });
  segment("gen-kind", v => { state.general.kind = v; refreshStats(); });
  segment("gen-quality", v => { state.general.quality = v; refreshStats(); });
  segment("doc-kind", v => {
    state.docs.kind = v;
    const manga = v === "manga";
    $("doc-lede").textContent = manga
      ? "Paste a public or account-authorized manga/manhwa chapter. Its pages are saved in an ordered folder, PDF, and CBZ."
      : "Paste a direct document or ebook link, or a page that links to files. Valid downloads keep their original format.";
    $("pdf-url").placeholder = manga
      ? "https://example.com/series/chapter-12"
      : "https://example.com/book.epub or a document index";
    $("doc-limit-label").textContent = manga ? "Page limit" : "Link limit";
    $("doc-limit-unit").textContent = manga ? "chapter pages" : "links checked";
    $("pdf-limit").placeholder = manga ? "500" : "200";
    $("doc-format-note").textContent = manga
      ? "Images are resolved with gallery-dl first, then standard page markup, and named 00001, 00002, ... in reading order."
      : "Files are checked from their contents, not just their names. Common documents, Office files, ebooks, comic archives, and text formats are supported.";
    $("doc-warning").textContent = manga
      ? "Only download chapters you have the right to save. DRM, paywalls, and access controls are not bypassed."
      : "Sites that build their viewer in JavaScript can hide the real file. Open the document itself and paste that address when an index page finds nothing.";
    refreshStats();
  });

  $("console-clear").onclick = () => { $("console").innerHTML = ""; };
  $("console-copy").onclick = () => {
    const text = $("console").innerText;
    // navigator.clipboard is not usable in the Android WebView — the page is
    // loaded over file://, and writeText is refused there — so the app's own
    // clipboard answers instead. Without this the button threw on the missing
    // API and did nothing at all, not even report a failure.
    const viaBridge = () => Promise.resolve(api().copy_text(text));
    const written = (navigator.clipboard && navigator.clipboard.writeText)
      ? navigator.clipboard.writeText(text).catch(viaBridge)
      : viaBridge();
    written.then(() => toast("Activity copied.", "ok"),
                 () => toast("Could not copy.", "err"));
  };

  segment("format", v => { state.format = v; api().set_option("format", v); refreshStats(); });
  segment("quality", v => { state.quality = v; api().set_option("quality", v); refreshStats(); });
  segment("proxy-type", v => { state.proxy_type = v; api().set_option("proxy_type", v); refreshStats(); });

  $("proxy-toggle").onclick = () => {
    state.proxy_enabled = !state.proxy_enabled;
    $("proxy-toggle").setAttribute("aria-checked", String(state.proxy_enabled));
    api().set_option("proxy_enabled", state.proxy_enabled);
    refreshStats();
  };
  $("proxy-url").onchange = () => api().set_option("proxy_url", $("proxy-url").value.trim());
  $("youtube-po-token").onchange = () => {
    state.youtube_po_token = $("youtube-po-token").value.trim();
    api().set_option("youtube_po_token", state.youtube_po_token);
  };
  $("test-proxy").onclick = () => api().test_proxy();
  document.querySelectorAll("[data-preset]").forEach(b => {
    b.onclick = () => {
      const [type, url] = b.dataset.preset.split("|");
      api().set_preset(type, url);
    };
  });

  $("folder").onchange = () => api().set_option("folder", $("folder").value.trim());
  $("browse").onclick = () => api().browse();
  $("open-folder").onclick = () => api().open_folder();
  document.querySelectorAll("[data-converter-mode]").forEach(button => {
    button.onclick = () => {
      $("media-convert-format").value = button.dataset.converterMode === "audio" ? "mp3" : "mp4";
      paintConverter();
    };
  });
  document.querySelectorAll(".format-picker [data-format]").forEach(button => {
    button.onclick = () => {
      $("media-convert-format").value = button.dataset.format;
      paintConverter();
    };
  });
  $("media-convert-resize").onchange = paintConverter;
  $("media-convert-fps").onchange = paintConverter;
  $("convert-media").onclick = () => api().convert_media(converterOptions());
  $("convert-document").onclick = () => api().convert_document();
  $("convert-image-folder").onclick = () => api().convert_image_folder();
  $("check-setup").onclick = () => api().check_setup();
  [$("update-btn"), $("update-components")].forEach(b => { b.onclick = () => api().update_tools(); });
  $("about").onclick = () => api().about();
}

function boot() {
  if (boot.done) return;
  boot.done = true;
  if (window.AndroidBridge) {
    /* Apply Android-only tablet and large-display ratios before building the
       navigation, avoiding a desktop-shaped first frame on wide devices. */
    document.documentElement.classList.add("android");
  }
  buildNav();
  setupPhone();
  if (window.AndroidBridge) {
    $("folder").readOnly = true;
    $("browse").textContent = "Choose parent folder";
    $("folder-note").innerHTML = "Android saves into <b>BlueKnight Downloader</b>, then sorts files into the same source folders as desktop.";
  }
  wire();
  paintConverter();
  // Every process launch starts dark. The theme button can switch the current
  // session, but a prior light choice never causes a bright startup flash.
  applyTheme("dark");
  document.documentElement.dataset.mode = state.source;
  refreshStats();
  setReady(false);
  api().hello().then(s => {
    state.format = s.format; state.quality = s.quality;
    state.folder = s.folder;
    state.youtube_po_token = s.youtube_po_token || "";
    state.proxy_enabled = s.proxy_enabled;
    state.proxy_type = s.proxy_type;
    setSegment("format", s.format);
    setSegment("quality", s.quality);
    setSegment("proxy-type", s.proxy_type);
    $("folder").value = window.AndroidBridge ? "BlueKnight Downloader" : s.folder;
    $("proxy-url").value = s.proxy_url;
    $("youtube-po-token").value = state.youtube_po_token;
    $("proxy-toggle").setAttribute("aria-checked", String(s.proxy_enabled));
    refreshStats();
  });
  // Whether a session is already stored is the first thing worth knowing.
  api().cookie_status().then(status => { state.cookies = status || {}; paintSignin(); });
  pump();
  // Setup can stall on a blocked network. Never trap the window behind the gate.
  setTimeout(() => { $("gate-skip").hidden = false; }, 12000);
}

$("gate-skip").onclick = () => { $("gate").hidden = true; };

window.addEventListener("pywebviewready", boot);
// pywebviewready can fire before this script parses, so check directly too.
if (window.pywebview && window.pywebview.api) boot();
else setTimeout(function retry() {
  if (window.pywebview && window.pywebview.api) boot(); else setTimeout(retry, 120);
}, 120);
