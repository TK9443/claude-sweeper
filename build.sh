#!/usr/bin/env bash
# Builds Claude Sweeper.app, signs it, installs it to /Applications and clears the staging directory.
# Nothing built is left inside the repo: Spotlight indexes any .app under build/ or dist/.
#
#   ./build.sh              build, sign, install to /Applications, launch
#   ./build.sh --no-install build and sign only, leave the path printed
#   ./build.sh --no-pin     install without touching the Dock
#   ./build.sh --dmg        build a release disk image instead of installing
#
# Signs ad-hoc unless CLAUDE_SWEEPER_SIGN_IDENTITY names a codesigning identity in the keychain;
# a named identity signs with the hardened runtime and a secure timestamp. With --dmg, setting
# CLAUDE_SWEEPER_NOTARY_PROFILE to a `notarytool store-credentials` profile also notarises and
# staples the image.
#
# Node is bundled into the app from whatever `node` is on PATH, which must be an official
# nodejs.org build: a Homebrew Node links libraries that will not exist on the user's Mac.

set -euo pipefail
cd "$(dirname "$0")"

REPO="$PWD"
STAGE="${TMPDIR:-/tmp/}claude-sweeper-build"
APP="$STAGE/dist/Claude Sweeper.app"
INSTALLED="/Applications/Claude Sweeper.app"
IDENTITY="${CLAUDE_SWEEPER_SIGN_IDENTITY:-}"
VERSION="$(sed -n 's/^__version__ = "\(.*\)"/\1/p' claude_sweeper/__init__.py)"

INSTALL=1
PIN=1
DMG=0
for argument in "$@"; do
    case "$argument" in
        --no-install) INSTALL=0 ;;
        --no-pin) PIN=0 ;;
        --dmg) DMG=1; INSTALL=0 ;;
        *) echo "unknown argument: $argument" >&2; exit 2 ;;
    esac
done

export PATH="$HOME/.local/bin:$PATH"
for node_bin in "$HOME"/.local/node-*/bin; do [ -d "$node_bin" ] && export PATH="$node_bin:$PATH"; done
command -v uv >/dev/null 2>&1 || { echo "uv not found" >&2; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "npm not found; the purge engine needs Node" >&2; exit 1; }

CLAUDE_SWEEPER_NODE="$(command -v node)"
if otool -L "$CLAUDE_SWEEPER_NODE" | tail -n +2 | grep -v -E '^\s+/(usr/lib|System)/' | grep -q .; then
    echo "$CLAUDE_SWEEPER_NODE links libraries outside the OS; bundle an official nodejs.org build" >&2
    exit 1
fi
export CLAUDE_SWEEPER_NODE

echo "==> environment"
uv sync --quiet
(cd purge && npm ci --no-audit --no-fund --silent)
[ -d purge/node_modules/classic-level ] || { echo "npm ci left no classic-level" >&2; exit 1; }

echo "==> build"
rm -rf "$STAGE"
mkdir -p "$STAGE"
uv run pyinstaller --noconfirm --distpath "$STAGE/dist" --workpath "$STAGE/work" "$REPO/ClaudeSweeper.spec"
[ -d "$APP" ] || { echo "PyInstaller produced no $APP" >&2; exit 1; }

echo "==> sign"
# Ad-hoc is fine for a local install: the app asks for no TCC grant that a changing signature would
# drop. A real identity needs the login keychain, which an SSH session cannot unlock
# (errSecInternalComponent). --deep applies the entitlements to the bundled node too, which is the
# one binary that needs them.
signed=0
if [ -n "$IDENTITY" ] && security find-identity -v -p codesigning 2>/dev/null | grep -qF "$IDENTITY"; then
    if codesign --force --deep --options runtime --timestamp --entitlements "$REPO/macos/entitlements.plist" \
        --identifier co.uk.kalkman.claudesweeper --sign "$IDENTITY" "$APP"; then
        signed=1
    else
        echo "the login keychain would not release $IDENTITY - signing ad-hoc instead"
    fi
fi
if [ "$signed" -eq 0 ]; then
    [ "$DMG" -eq 1 ] && { echo "a release image needs CLAUDE_SWEEPER_SIGN_IDENTITY" >&2; exit 1; }
    codesign --force --deep --sign - --identifier co.uk.kalkman.claudesweeper "$APP"
fi
codesign --verify --deep --strict "$APP"
codesign -dvv "$APP" 2>&1 | grep -E '^(Identifier|Signature|Authority)' || true

if [ "$DMG" -eq 1 ]; then
    echo "==> disk image"
    IMAGE="${TMPDIR:-/tmp/}ClaudeSweeper-$VERSION-macos-arm64.dmg"
    mkdir -p "$STAGE/image"
    ditto "$APP" "$STAGE/image/Claude Sweeper.app"
    ln -s /Applications "$STAGE/image/Applications"
    rm -f "$IMAGE"
    hdiutil create -quiet -volname "Claude Sweeper" -srcfolder "$STAGE/image" -format UDZO "$IMAGE"
    codesign --force --timestamp --sign "$IDENTITY" "$IMAGE"
    if [ -n "${CLAUDE_SWEEPER_NOTARY_PROFILE:-}" ]; then
        echo "==> notarise"
        xcrun notarytool submit "$IMAGE" --keychain-profile "$CLAUDE_SWEEPER_NOTARY_PROFILE" --wait
        xcrun stapler staple "$IMAGE"
        spctl --assess --type open --context context:primary-signature -vv "$IMAGE"
    fi
    rm -rf "$STAGE"
    echo "built $IMAGE"
    exit 0
fi

if [ "$INSTALL" -eq 0 ]; then
    echo "built $APP  (not installed; delete it when you are done)"
    exit 0
fi

echo "==> install"
osascript -e 'quit app "Claude Sweeper"' >/dev/null 2>&1 || pkill -x ClaudeSweeper || true
sleep 1
rm -rf "$INSTALLED"
ditto "$APP" "$INSTALLED"
rm -rf "$STAGE"

if [ "$PIN" -eq 1 ] && ! defaults read com.apple.dock persistent-apps 2>/dev/null | grep -q "Claude%20Sweeper.app\|Claude Sweeper.app"; then
    echo "==> dock"
    defaults write com.apple.dock persistent-apps -array-add "<dict><key>tile-data</key><dict><key>file-data</key><dict><key>_CFURLString</key><string>$INSTALLED</string><key>_CFURLStringType</key><integer>0</integer></dict></dict></dict>"
    killall Dock
fi

# Driven over SSH there is no GUI session to launch into, so this is reported, never fatal.
if open "$INSTALLED" 2>/dev/null; then
    echo "installed and launched $INSTALLED"
else
    echo "installed $INSTALLED - could not launch it from this session"
fi
