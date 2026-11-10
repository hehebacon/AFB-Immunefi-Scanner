#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

fail() {
  printf '\n[AFB] ERROR: %s\n' "$*" >&2
  exit 1
}

printf '\n============================================\n'
printf '  AFB - Smart Contract Analysis UI\n'
printf '============================================\n'

command -v python3 >/dev/null 2>&1 || fail "Python 3 is missing. Install it with: sudo apt install python3 python3-venv python3-pip"

PYTHON_VERSION="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' \
  || fail "Python 3.11 or newer is required (found $PYTHON_VERSION)."

python3 -c 'import tkinter' >/dev/null 2>&1 || fail "Tkinter is missing. On Kali/Debian install it with: sudo apt install python3-tk"

python3 -m venv --help >/dev/null 2>&1 || fail "Python venv support is missing. Install it with: sudo apt install python3-venv"

VENV="$ROOT/.venv"
if [[ ! -x "$VENV/bin/python" ]]; then
  printf '[AFB] Creating virtual environment...\n'
  python3 -m venv "$VENV" || fail "Could not create .venv. Check that python3-venv is installed."
fi

PY="$VENV/bin/python"
printf '[AFB] Checking and installing project dependencies...\n'
"$PY" -m pip install --disable-pip-version-check --upgrade pip
"$PY" -m pip install --disable-pip-version-check -e '.[analysis]'

printf '\n[AFB] Environment checks passed.\n'
printf '[AFB] Optional external tools:\n'
for tool in slither aderyn forge echidna; do
  if command -v "$tool" >/dev/null 2>&1; then
    printf '  [OK] %s\n' "$tool"
  else
    printf '  [--] %s not installed (related analysis layer may be unavailable)\n' "$tool"
  fi
done

printf '\n[AFB] Launching desktop UI...\n'
exec "$PY" "$ROOT/intro.py"
