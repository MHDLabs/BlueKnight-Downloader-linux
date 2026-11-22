"use strict";

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
    closeSheet({ restoreFocus: false });
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
    if (note) note.textContent = saved && saved.signed_in ? "✓ " + saved.detail : "";
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

