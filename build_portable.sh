#!/usr/bin/env bash
# Build Blue Knight Downloader for Linux or macOS.
#
# The Windows counterpart is build_portable.ps1. This does the same job with
# two differences forced by the platform: the bundled tools are fetched here
# rather than committed (the Linux and macOS binaries are ~200 MB the Windows
# build already has in vendor/), and there is no Tcl/Tk to carry, because
# pywebview draws its dialogs with GTK/WebKit on Linux and Cocoa on macOS.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENDOR="$ROOT/vendor"
OUTPUT="$ROOT/release"
WORK="$ROOT/build"
FLAVOR="${BLUEKNIGHT_FLAVOR:-full}"
while [ "$#" -gt 0 ]; do
    case "$1" in
        --flavor)
            [ "$#" -ge 2 ] || { echo "Missing value for --flavor" >&2; exit 2; }
            FLAVOR="$2"
            shift 2
            ;;
        --flavor=*)
            FLAVOR="${1#*=}"
            shift
            ;;
        *)
            echo "Unknown argument: $1" >&2
            exit 2
            ;;
    esac
done
case "$FLAVOR" in
    lite|full) ;;
    *) echo "Flavor must be 'lite' or 'full' (got '$FLAVOR')." >&2; exit 2 ;;
esac

SPOTDL_VERSION="4.5.2"
YTJS_VERSION="18.0.0"
case "$(uname -s)" in
    Darwin) OS_TAG=mac ;;
    Linux)  OS_TAG=linux ;;
    *) echo "Use build_portable.ps1 on Windows." >&2; exit 1 ;;
esac
case "$(uname -m)" in
    arm64|aarch64) ARCH=arm64 ;;
    *) ARCH=x64 ;;
esac
if [ "$OS_TAG" != "linux" ] && [ "$FLAVOR" = "lite" ]; then
    echo "The Lite flavor is currently available for Linux only." >&2
    exit 2
fi
echo "Building for $OS_TAG/$ARCH ($FLAVOR)"

# --------------------------------------------------------------------------
# pywebview has no window to draw on a Linux box without the WebKit GTK
# bindings, and it fails at import rather than at startup. Say so now, with
# the command that fixes it, instead of shipping an executable that cannot open.
# --------------------------------------------------------------------------
if [ "$OS_TAG" = linux ]; then
    # 4.1 on current distributions, 4.0 on anything Ubuntu 22.04 vintage.
    # pywebview accepts either, so requiring 4.1 would fail a machine that works.
    if ! python3 - <<'PROBE' 2>/dev/null
import gi
for version in ("4.1", "4.0"):
    try:
        gi.require_version("WebKit2", version)
        break
    except ValueError:
        continue
else:
    raise SystemExit(1)
PROBE
    then
        echo "ERROR: pywebview needs the WebKit2 GTK bindings." >&2
        echo "  Debian/Ubuntu: sudo apt install python3-gi gir1.2-webkit2-4.1 libcairo2-dev" >&2
        echo "  Fedora:        sudo dnf install python3-gobject webkit2gtk4.1" >&2
        echo "  Arch:          sudo pacman -S python-gobject webkit2gtk-4.1" >&2
        exit 1
    fi
fi

fetch() {  # fetch <url> <destination>
    echo "  fetching $(basename "$2")"
    curl --fail --location --silent --show-error --retry 3 -o "$2" "$1"
}

rm -rf "$OUTPUT" "$WORK"
mkdir -p "$VENDOR" "$OUTPUT" "$WORK"
printf '%s\n' "$FLAVOR" > "$OUTPUT/release-flavor.txt"

if [ "$FLAVOR" = "full" ]; then
# --- spotDL, yt-dlp, Deno: one release binary each -------------------------
if [ "$OS_TAG" = mac ]; then
    SPOTDL_ASSET="spotdl-${SPOTDL_VERSION}-darwin"
    YTDLP_ASSET="yt-dlp_macos"
    DENO_ASSET="deno-$([ "$ARCH" = arm64 ] && echo aarch64 || echo x86_64)-apple-darwin.zip"
else
    SPOTDL_ASSET="spotdl-${SPOTDL_VERSION}-linux"
    YTDLP_ASSET="yt-dlp_linux$([ "$ARCH" = arm64 ] && echo _aarch64 || echo '')"
    DENO_ASSET="deno-$([ "$ARCH" = arm64 ] && echo aarch64 || echo x86_64)-unknown-linux-gnu.zip"
fi

[ -f "$VENDOR/spotdl" ] || fetch \
    "https://github.com/spotDL/spotify-downloader/releases/download/v${SPOTDL_VERSION}/${SPOTDL_ASSET}" \
    "$VENDOR/spotdl"
[ -f "$VENDOR/yt-dlp" ] || fetch \
    "https://github.com/yt-dlp/yt-dlp/releases/latest/download/${YTDLP_ASSET}" \
    "$VENDOR/yt-dlp"
if [ ! -f "$VENDOR/deno" ]; then
    fetch "https://github.com/denoland/deno/releases/latest/download/${DENO_ASSET}" "$VENDOR/deno.zip"
    (cd "$VENDOR" && unzip -o -q deno.zip deno && rm -f deno.zip)
fi

# --- FFmpeg: no single project publishes every platform --------------------
if [ ! -f "$VENDOR/ffmpeg" ] || [ ! -f "$VENDOR/ffprobe" ]; then
    if [ "$OS_TAG" = mac ]; then
        fetch "https://evermeet.cx/ffmpeg/getrelease/ffmpeg/zip" "$VENDOR/ffmpeg.zip"
        fetch "https://evermeet.cx/ffmpeg/getrelease/ffprobe/zip" "$VENDOR/ffprobe.zip"
        (cd "$VENDOR" && unzip -o -q -j ffmpeg.zip ffmpeg && unzip -o -q -j ffprobe.zip ffprobe \
            && rm -f ffmpeg.zip ffprobe.zip)
    else
        SUFFIX=$([ "$ARCH" = arm64 ] && echo linuxarm64 || echo linux64)
        fetch "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-${SUFFIX}-gpl.tar.xz" \
              "$VENDOR/ffmpeg.tar.xz"
        tar -xJf "$VENDOR/ffmpeg.tar.xz" -C "$VENDOR" --strip-components=2 \
            --wildcards '*/bin/ffmpeg' '*/bin/ffprobe'
        rm -f "$VENDOR/ffmpeg.tar.xz"
    fi
fi

chmod +x "$VENDOR/spotdl" "$VENDOR/yt-dlp" "$VENDOR/deno" "$VENDOR/ffmpeg" "$VENDOR/ffprobe"

# A downloaded file of plausible size can still be a mirror's error page. The
# Windows build makes FFmpeg prove it launches before bundling; so does this.
FFMPEG_BANNER="$("$VENDOR/ffmpeg" -version | head -n 1)"
echo "Bundling $FFMPEG_BANNER"
fi

# gallery-dl imports each site's extractor by name at runtime, so a normal
# import scan finds none of them and the frozen app would be able to do yt-dlp
# only. --collect-all is what puts the extractors (and requests) inside it.
PYI_ARGS=(
    --noconfirm --clean --windowed --onefile
    --name BlueKnightDownloader
    --distpath "$OUTPUT" --workpath "$WORK" --specpath "$WORK"
    --collect-all webview
    --collect-all gallery_dl
    --collect-all streamlink
    --collect-all requests
    --collect-all certifi
    --collect-all PIL
    --collect-all pikepdf
    --hidden-import img2pdf
    --add-data "$ROOT/web:web"
    --add-data "$ROOT/assets:assets"
    --add-data "$OUTPUT/release-flavor.txt:."
)

if [ "$FLAVOR" = "full" ]; then
    PYI_ARGS+=(--add-binary "$VENDOR/spotdl:tools")
    PYI_ARGS+=(--add-binary "$VENDOR/yt-dlp:tools")
    PYI_ARGS+=(--add-binary "$VENDOR/deno:tools")
    PYI_ARGS+=(--add-binary "$VENDOR/ffmpeg:tools")
    PYI_ARGS+=(--add-binary "$VENDOR/ffprobe:tools")
fi

if [ "$FLAVOR" = "full" ]; then
# The desktop's second YouTube engine, built from source rather than fetched:
# it is our own wrapper around YoutubeExplode and the .NET SDK is all it needs.
# A clone without the SDK still produces a working app, one engine shorter.
YOUTUBE_EXPLODE="$VENDOR/blueknight-youtube"
if [ ! -f "$YOUTUBE_EXPLODE" ]; then
    if command -v dotnet >/dev/null 2>&1; then
        echo "  building the YoutubeExplode engine"
        case "$OS_TAG:$ARCH" in
            mac:arm64)   RID=osx-arm64 ;;
            mac:*)       RID=osx-x64 ;;
            linux:arm64) RID=linux-arm64 ;;
            *)           RID=linux-x64 ;;
        esac
        dotnet publish "$ROOT/dotnet/BlueKnightYoutube/BlueKnightYoutube.csproj"             -c Release -r "$RID" --property:PublishDir="$WORK/dotnet/"
        _size=$(wc -c < "$WORK/dotnet/blueknight-youtube")
        if [ "$_size" -lt 20000000 ]; then
            echo "the engine published at $_size bytes: that is a framework-dependent build, not a self-contained one" >&2
            exit 1
        fi
        cp "$WORK/dotnet/blueknight-youtube" "$YOUTUBE_EXPLODE"
        chmod +x "$YOUTUBE_EXPLODE"
    else
        echo "  no .NET SDK: building without the YoutubeExplode fallback engine" >&2
    fi
fi
[ -f "$YOUTUBE_EXPLODE" ] && PYI_ARGS+=(--add-binary "$YOUTUBE_EXPLODE:tools")

fi

# The YouTube.js engine: our two scripts plus the library, bundled as one file.
# Both flavors include the small resolver; Lite fetches Deno only when needed.
YTJS_BUNDLE="$ROOT/engines/youtubejs/youtubei.bundle.mjs"
if [ ! -f "$YTJS_BUNDLE" ]; then
    echo "  fetching the YouTube.js library"
    curl --fail --location --retry 3 -o "$YTJS_BUNDLE"         "https://esm.sh/youtubei.js@$YTJS_VERSION/denonext/youtubei.bundle.mjs"
fi
PYI_ARGS+=(--add-data "$ROOT/engines/youtubejs:tools")

if [ "$FLAVOR" = "full" ]; then
# The NewPipe engine and a runtime to run it in. Full builds include the JVM fallback.
NEWPIPE_JAR="$VENDOR/blueknight-newpipe.jar"
if [ ! -f "$NEWPIPE_JAR" ] && command -v java >/dev/null 2>&1; then
    echo "  building the NewPipe engine"
    # The JVM helper owns this wrapper independently of the removed mobile app.
    sh "$ROOT/jvm/gradlew" -p "$ROOT/jvm/newpipe" --no-daemon -q shadowJar
    cp "$ROOT/jvm/newpipe/build/libs/blueknight-newpipe.jar" "$NEWPIPE_JAR"
fi
if [ -f "$NEWPIPE_JAR" ]; then
    PYI_ARGS+=(--add-data "$NEWPIPE_JAR:tools")
    if [ ! -d "$VENDOR/jre" ] && command -v jlink >/dev/null 2>&1; then
        echo "  building a Java runtime for it"
        jlink --add-modules java.base,java.net.http,java.naming,jdk.crypto.ec               --strip-debug --no-header-files --no-man-pages --compress=2               --output "$VENDOR/jre"
    fi
    [ -d "$VENDOR/jre" ] && PYI_ARGS+=(--add-data "$VENDOR/jre:tools/jre")
fi
fi
if [ "$OS_TAG" = mac ]; then
    # .icns is the only icon format a bundle accepts; skip rather than fail
    # the build when only the Windows .ico has been checked in.
    [ -f "$ROOT/assets/icon.icns" ] && PYI_ARGS+=(--icon "$ROOT/assets/icon.icns")
    PYI_ARGS+=(--osx-bundle-identifier net.blueknight.downloader)
fi

python3 -m PyInstaller "${PYI_ARGS[@]}" "$ROOT/spotify_downloader.py"

cp "$ROOT/README.md" "$ROOT/THIRD_PARTY_NOTICES.txt" "$ROOT/LICENSE" "$OUTPUT/"

cd "$OUTPUT"
if [ "$OS_TAG" = mac ]; then
    # Ship the .app, not the bare Unix executable beside it: double-clicking
    # the latter opens a terminal, and Gatekeeper treats it differently.
    PACKAGE="BlueKnightDownloader-macos-${ARCH}.zip"
    ditto -c -k --sequesterRsrc --keepParent BlueKnightDownloader.app "$PACKAGE"
    zip -q "$PACKAGE" README.md THIRD_PARTY_NOTICES.txt LICENSE
    echo "Application bundle created at $OUTPUT/BlueKnightDownloader.app"
else
    PACKAGE="BlueKnightDownloader-linux-${ARCH}-${FLAVOR}.tar.gz"
    : > portable.mode
    tar -czf "$PACKAGE" BlueKnightDownloader portable.mode release-flavor.txt README.md THIRD_PARTY_NOTICES.txt LICENSE
    echo "Standalone executable created at $OUTPUT/BlueKnightDownloader"
fi
echo "Release package created at $OUTPUT/$PACKAGE"
