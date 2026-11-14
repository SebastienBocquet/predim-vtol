#!/bin/sh
# One-line installer of predim-vtol for Linux and macOS, published with each release:
#   curl -LsSf https://github.com/SebastienBocquet/predim-vtol/releases/latest/download/install.sh | sh
# Installs uv if needed (in ~/.local/bin), then predim-vtol with its own Python 3.12 and the
# dependency versions of the release (the same as the Windows package). No root rights.
# The release workflow replaces @VERSION@ by the released version.
set -eu

VERSION="${PREDIM_VTOL_VERSION:-@VERSION@}"
BASE="${PREDIM_VTOL_BASE:-https://github.com/SebastienBocquet/predim-vtol/releases/download/v$VERSION}"
WHEEL="predim_vtol-$VERSION-py3-none-any.whl"

say() { printf '%s\n' "$*"; }

if command -v uv >/dev/null 2>&1; then
    UV=uv
elif [ -x "$HOME/.local/bin/uv" ]; then
    UV="$HOME/.local/bin/uv"
else
    say "[1/3] Installing uv, the Python package manager (in ~/.local/bin)"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    UV="$HOME/.local/bin/uv"
fi

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT INT TERM

say "[2/3] Downloading predim-vtol $VERSION"
curl -LsSf -o "$TMP/$WHEEL" "$BASE/$WHEEL"
curl -LsSf -o "$TMP/constraints.txt" "$BASE/constraints.txt"

say "[3/3] Installing predim-vtol and its dependencies (several minutes the first time)"
"$UV" tool install --force --python 3.12 --constraints "$TMP/constraints.txt" \
    "predim-vtol[ui,mdo] @ file://$TMP/$WHEEL"
# Puts ~/.local/bin in the PATH of the shell profiles, unless UV_NO_MODIFY_PATH is set.
[ -n "${UV_NO_MODIFY_PATH:-}" ] || "$UV" tool update-shell >/dev/null 2>&1 || true

# Without this file, Streamlit asks for an e-mail address at the first launch.
if [ ! -f "$HOME/.streamlit/credentials.toml" ]; then
    mkdir -p "$HOME/.streamlit"
    printf '[general]\nemail = ""\n' >"$HOME/.streamlit/credentials.toml"
fi

BIN="$("$UV" tool dir --bin)/predim-vtol"
if [ "$(uname -s)" = "Linux" ]; then
    APPS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
    mkdir -p "$APPS"
    cat >"$APPS/predim-vtol.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Predim VTOL
Comment=Pre-sizing of RC VTOL aircraft (close the terminal to stop)
Exec=$BIN --browser.gatherUsageStats=false
Terminal=true
Categories=Science;Engineering;
EOF
fi

say ""
say "predim-vtol $VERSION is installed."
say "Start it with:  predim-vtol"
say "(open a new terminal first if the command is not found; on Linux it is also in the"
say "applications menu as 'Predim VTOL'). It opens in your web browser; press Ctrl+C in the"
say "terminal to stop it. Uninstall:  uv tool uninstall predim-vtol"
