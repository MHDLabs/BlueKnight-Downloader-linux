/* Browser-only adapter for the GitHub Pages preview.
 * This file is injected only into the generated Pages site, never the desktop index.
 */
(() => {
  "use strict";

  const queue = [];
  const settings = {
    format: "mp3", quality: "320", proxy_enabled: false,
    proxy_type: "http", proxy_url: "http://127.0.0.1:10809",
    youtube_po_token: "", folder: "~/Downloads/BlueKnight",
  };
  let started = false;
  let jobSequence = 0;
  let activeJob = null;

  const emit = (name, ...args) => queue.push([name, args]);
  const log = (message, level = "info") => emit("log", [[message, level]]);
  const toast = (message, level = "info") => emit("toast", message, level);

  function setupDemo() {
    if (started) return;
    started = true;
    log("Welcome to Blue Knight Downloader.", "success");
    log("Public interactive demo. No local tools are connected.", "info");
    emit("setup", "Preparing demo…", "Loading the sample environment");
    emit("status", "Demo");
    window.setTimeout(() => {
      emit("components", [
        "Mode: browser demo (simulated)",
        "FFmpeg: preview only", "spotDL: preview only",
        "yt-dlp: preview only", "Deno: preview only",
        "Local files and sign-in: unavailable in demo",
      ].join("\n"));
      emit("setup_done");
      toast("Live demo is ready. Downloads are simulated; no files are created.", "info");
    }, 450);
  }

  function cancelActiveJob() {
    if (!activeJob) return false;
    activeJob.timers.forEach(window.clearTimeout);
    activeJob = null;
    emit("stage", "Demo task cancelled");
    log("Demo task cancelled by the user.", "warning");
    emit("finished");
    return true;
  }

  function startDemoJob(kind, url, label, formatLabel = "media file") {
    if (activeJob) {
      toast("A demo task is already running. Stop it before starting another.", "err");
      return;
    }
    const id = ++jobSequence;
    const output = "~/Downloads/BlueKnight/Demo/" + label.replace(/[^a-z0-9_-]+/gi, "-");
    const startedAt = Date.now();
    const job = { id, timers: [] };
    activeJob = job;

    emit("status", "Downloading");
    emit("plan", 1, 1, output);
    log("DEMO · " + label, "success");
    log("Input: " + url, "info");
    log("Simulated run. No request is sent to the media source.", "warning");

    const steps = [
      [350, () => {
        emit("stage", "Validating the sample URL…");
        log("URL accepted by the demo adapter.", "info");
      }],
      [900, () => {
        emit("stage", "Resolving media information…");
        log("Sample metadata resolved.", "success");
        emit("track", 1, 1, label);
      }],
      [1500, () => {
        emit("stage", "Selecting a sample stream…");
        emit("bytes", 18, label, "1.8 MiB/s", "00:04");
      }],
      [2100, () => {
        emit("stage", "Simulating transfer…");
        emit("bytes", 47, label, "2.4 MiB/s", "00:02");
      }],
      [2700, () => {
        emit("stage", "Simulating finalization…");
        emit("bytes", 84, label, "2.2 MiB/s", "00:01");
      }],
      [3300, () => {
        if (!activeJob || activeJob.id !== id) return;
        emit("bytes", 100, label, "", "");
        log("Demo output would be saved as: " + output + "." + formatLabel, "success");
        log("No file was actually downloaded or written to disk.", "warning");
        activeJob = null;
        emit("success", (Date.now() - startedAt) / 1000);
        emit("finished");
        toast("Demo complete. The real app is required to download files.", "info");
      }],
    ];
    for (const [delay, action] of steps) {
      job.timers.push(window.setTimeout(() => {
        if (activeJob && activeJob.id === id) action();
      }, delay));
    }
  }

  const unavailable = (feature) => {
    toast(feature + " needs the installed desktop app and is disabled in this browser demo.", "info");
  };

  const api = Object.freeze({
    hello() {
      setupDemo();
      return Promise.resolve({
        format: settings.format, quality: settings.quality,
        proxy_enabled: settings.proxy_enabled, proxy_type: settings.proxy_type,
        proxy_url: settings.proxy_url, youtube_po_token: settings.youtube_po_token,
        folder: settings.folder,
      });
    },
    poll() {
      return Promise.resolve(queue.splice(0, queue.length));
    },
    set_option(name, value) {
      if (Object.prototype.hasOwnProperty.call(settings, name)) settings[name] = value;
      return Promise.resolve();
    },
    minimize() {
      unavailable("Window controls");
    },
    toggle_maximize() {
      if (!document.fullscreenElement && document.documentElement.requestFullscreen) {
        return document.documentElement.requestFullscreen().catch(() => unavailable("Fullscreen"));
      }
      if (document.fullscreenElement && document.exitFullscreen) {
        return document.exitFullscreen().catch(() => unavailable("Fullscreen"));
      }
      unavailable("Fullscreen");
      return Promise.resolve();
    },
    close() {
      toast("Close this browser tab to leave the live demo.", "info");
    },
    start_download(url, fmt, quality) {
      const valid = /^https?:\/\/open\.spotify\.com\/(track|album|playlist)\//i.test(url || "");
      if (!valid) {
        emit("failure", "For the Spotify demo, enter a Spotify track, album, or playlist link.");
        emit("finished");
        return;
      }
      settings.format = fmt || settings.format;
      settings.quality = quality || settings.quality;
      startDemoJob("spotify", url, "Spotify sample", settings.format);
    },
    start_media(kind, url, quality, audioOnly, limit) {
      const names = {
        youtube: "YouTube", ytmusic: "YouTube Music", tiktok: "TikTok",
        instagram: "Instagram", soundcloud: "SoundCloud", x: "X", general: "Video",
      };
      const label = names[kind] || "Media";
      const mode = audioOnly ? "audio" : "video";
      startDemoJob(kind, url, label + " " + mode + " sample", mode);
    },
    start_pdf(url, limit) {
      startDemoJob("pdf", url, "Document sample", "pdf");
    },
    start_manga(url, limit) {
      startDemoJob("manga", url, "Chapter sample", "cbz");
    },
    stop_download() {
      if (!cancelActiveJob()) toast("There is no active demo task.", "info");
    },
    set_preset(proxyType, url) {
      settings.proxy_type = proxyType;
      settings.proxy_url = url;
      settings.proxy_enabled = true;
      emit("proxy", proxyType, url, true);
      toast("Proxy preset selected for preview only. No connection was made.", "info");
    },
    test_proxy() {
      toast("Proxy testing is disabled in the public demo. No network test was sent.", "info");
    },
    check_setup() {
      emit("setup", "Demo mode", "The browser preview does not install or inspect local tools.");
      window.setTimeout(() => {
        emit("components", "Browser demo · No local tools or files are connected.");
        emit("setup_done");
      }, 250);
    },
    sign_in(kind) {
      toast("Sign-in is disabled in the public demo. No account or cookie data is collected.", "info");
    },
    finish_sign_in() {
      unavailable("Sign-in");
    },
    cookie_status() {
      return Promise.resolve({
        youtube: { signed_in: false, detail: "Unavailable in demo" },
        instagram: { signed_in: false, detail: "Unavailable in demo" },
        tiktok: { signed_in: false, detail: "Unavailable in demo" },
        soundcloud: { signed_in: false, detail: "Unavailable in demo" },
        x: { signed_in: false, detail: "Unavailable in demo" },
      });
    },
    update_tools() {
      emit("updating", true);
      window.setTimeout(() => {
        emit("updating", false);
        toast("Component updates are available only in the installed desktop app.", "info");
      }, 350);
    },
    open_folder() {
      unavailable("Opening local folders");
    },
    open_telegram() {
      window.open("https://t.me/BlueKnight_Net", "_blank", "noopener,noreferrer");
    },
    clipboard() {
      const page = document.querySelector(".page.on")?.dataset.page || "youtube";
      const samples = {
        download: "https://open.spotify.com/track/11dFghVXANMlKmJXsNCbNl",
        youtube: "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        ytmusic: "https://music.youtube.com/watch?v=dQw4w9WgXcQ",
        tiktok: "https://www.tiktok.com/@demo/video/0000000000000000000",
        instagram: "https://www.instagram.com/p/demo/",
        soundcloud: "https://soundcloud.com/demo/sample-track",
        x: "https://x.com/demo/status/1",
        general: "https://example.com/sample-video",
      };
      return Promise.resolve(samples[page] || samples.youtube);
    },
    copy_text(text) {
      const field = document.createElement("textarea");
      field.value = String(text || "");
      field.setAttribute("readonly", "");
      field.style.position = "fixed";
      field.style.opacity = "0";
      document.body.appendChild(field);
      field.select();
      let copied = false;
      try { copied = document.execCommand("copy"); } catch (_) { copied = false; }
      field.remove();
      return Promise.resolve(copied);
    },
    about() {
      toast("Blue Knight Downloader · Public interactive demo · Sample data only.", "info");
    },
    browse() {
      unavailable("Choosing a local folder");
    },
    convert_media(options) {
      emit("converting", true, "media");
      window.setTimeout(() => {
        emit("converting", false, "media");
        toast("Media conversion is simulated in demo mode. No local file was read.", "info");
      }, 700);
    },
    convert_document() {
      unavailable("Document conversion");
    },
    convert_image_folder() {
      unavailable("Image-folder conversion");
    },
  });

  // Injected only into the Pages output; desktop keeps the native pywebview API.
  window.pywebview = { api };
})();
