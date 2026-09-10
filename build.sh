#!/usr/bin/env bash
# Builds Claude Sweeper.app, signs it, installs it to /Applications and clears the staging directory.
# Nothing built is left inside the repo: Spotlight indexes any .app under build/ or dist/.
#
#   ./build.sh              build, sign, install to /Applications, launch
#   ./build.sh --no-install build and sign only, leave the path printed
#   ./build.sh --no-pin     install without touching the Dock
#
# Signs ad-hoc unless CLAUDE_SWEEPER_SIGN_IDENTITY names a codesigning identity in the keychain.

set -euo pipefail
cd "$(dirname "$0")"

REPO="$PWD"
STAGE="${TMPDIR:-/tmp/}claude-sweeper-build"
APP="$STAGE/dist/Claude Sweeper.app"
INSTALLED="/Applications/Claude Sweeper.app"
IDENTITY="${CLAUDE_SWEEPER_SIGN_IDENTITY:-}"

INSTALL=1
PIN=1
for argument in "$@"; do
    case "$argument" in
        --no-install) INSTALL=0 ;;
        --no-pin) PIN=0 ;;
        *) echo "unknown argument: $argument" >&2; exit 2 ;;
    esac
done

export PATH="$HOME/.local/bin:$PATH"
for node_bin in "$HOME"/.local/node-*/bin; do [ -d "$node_bin" ] && export PATH="$node_bin:$PATH"; done
command -v uv >/dev/null 2>&1 || { echo "uv not found" >&2; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "npm not found; the purge engine needs Node" >&2; exit 1; }

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
# Ad-hoc is fine: the app asks for no TCC grant that a changing signature would drop. A real
# identity needs the login keychain, which an SSH session cannot unlock (errSecInternalComponent).
signed=0
if [ -n "$IDENTITY" ] && security find-identity -v -p codesigning 2>/dev/null | grep -qF "$IDENTITY"; then
    if codesign --force --deep --sign "$IDENTITY" --identifier co.uk.kalkman.claudesweeper "$APP" 2>/dev/null; then
        signed=1
    else
        echo "the login keychain would not release $IDENTITY - signing ad-hoc instead"
    fi
fi
if [ "$signed" -eq 0 ]; then
    codesign --force --deep --sign - --identifier co.uk.kalkman.claudesweeper "$APP"
fi
codesign --verify --strict "$APP"
codesign -dvv "$APP" 2>&1 | grep -E '^(Identifier|Signature|Authority)' || true

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
