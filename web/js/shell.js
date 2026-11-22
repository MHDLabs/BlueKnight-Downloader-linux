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
let sheetReturnFocus = null;
let sheetRestoreFocus = true;

function sheetFocusables() {
  return [...$("sheet").querySelectorAll(
    'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
  )].filter(el =>
    el.tabIndex >= 0 && !el.hidden && el.getAttribute("aria-hidden") !== "true" && el.getClientRects().length
  );
}

function handleSheetKeydown(event) {
  const sheet = $("sheet");
  if (sheet.hidden) return;

  if (event.key === "Escape") {
    event.preventDefault();
    closeSheet();
    return;
  }
  if (event.key !== "Tab") return;

  const focusables = sheetFocusables();
  if (!focusables.length) {
    event.preventDefault();
    $("sheet-close").focus();
    return;
  }

  const first = focusables[0];
  const last = focusables[focusables.length - 1];
  const outside = !sheet.contains(document.activeElement);
  if (event.shiftKey && (document.activeElement === first || outside)) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && (document.activeElement === last || outside)) {
    event.preventDefault();
    first.focus();
  }
}

function openSheet() {
  const current = document.querySelector(".page.on")?.dataset.page;
  // Only the tiles whose answer changed. Rewriting all twelve invalidated all
  // twelve, and the current-tile rule is the most expensive style on the page
  // — so every open was recalculating eleven tiles to tell them nothing.
  document.querySelectorAll("#sheet-grid .tile").forEach(t => {
    const now = String(t.dataset.target === current);
    if (t.getAttribute("aria-current") !== now) t.setAttribute("aria-current", now);
  });
  const sheet = $("sheet");
  if (sheet.hidden) {
    const active = document.activeElement;
    sheetReturnFocus = active && active !== document.body ? active : $("mbar-source");
    sheetRestoreFocus = true;
  }
  clearTimeout(sheetExit);
  sheet.classList.remove("closing");
  sheet.hidden = false;
  $("mbar-source").setAttribute("aria-expanded", "true");
  $("mbar-more").setAttribute("aria-expanded", "true");
  const selected = [...sheet.querySelectorAll("#sheet-grid .tile")]
    .find(tile => tile.getAttribute("aria-current") === "true");
  (selected || sheet.querySelector("#sheet-grid .tile"))?.focus();
}

function closeSheet({ restoreFocus = true } = {}) {
  const sheet = $("sheet");
  $("mbar-source").setAttribute("aria-expanded", "false");
  $("mbar-more").setAttribute("aria-expanded", "false");
  if (sheet.hidden || sheet.classList.contains("closing")) return;
  clearTimeout(sheetExit);
  sheetRestoreFocus = restoreFocus;
  sheet.classList.add("closing");
  sheetExit = setTimeout(() => {
    sheet.hidden = true;
    sheet.classList.remove("closing");
    const target = sheetReturnFocus;
    sheetReturnFocus = null;
    if (sheetRestoreFocus && target?.isConnected && typeof target.focus === "function") {
      target.focus();
    }
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

    // A phone sheet must not survive a rotation or resize into desktop layout.
    const sheet = $("sheet");
    if (!sheet.hidden) {
      const focusWasInside = sheet.contains(document.activeElement);
      clearTimeout(sheetExit);
      sheet.hidden = true;
      sheet.classList.remove("closing");
      sheetReturnFocus = null;
      $("mbar-source").setAttribute("aria-expanded", "false");
      $("mbar-more").setAttribute("aria-expanded", "false");
      if (focusWasInside) document.querySelector("#nav button.on")?.focus();
    }
    return;
  }
  // Theme is a property of the app, not of the section you are picking, so on
  // a phone it lives in the bar and is deliberately kept out of the sheet the
  // rest of .side-foot moves into.
  $("mbar").insertBefore(theme, $("mbar-more"));
  if (!setupPhone.done) {
    setupPhone.done = true;
    buildSheet();
    document.addEventListener("keydown", handleSheetKeydown);
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

