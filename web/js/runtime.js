"use strict";

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
