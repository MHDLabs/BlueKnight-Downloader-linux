"use strict";

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
    const selected = button.dataset.format === format;
    button.setAttribute("aria-checked", String(selected));
    button.tabIndex = selected ? 0 : -1;
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
  el.setAttribute("role", kind === "err" ? "alert" : "status");
  el.setAttribute("aria-atomic", "true");
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
  const value = Math.max(0, Math.min(100, Number(pct) || 0));
  const fill = $("bar-fill");
  fill.style.width = value + "%";
  fill.className = "bar-fill" + (kind ? " " + kind : "");
  $("stat-pct").textContent = Math.round(value) + "%";
  fill.parentElement?.setAttribute("aria-valuenow", String(Math.round(value)));
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

