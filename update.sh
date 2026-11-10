#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if ! command -v git >/dev/null 2>&1; then
  echo "[AFB] git is required." >&2; exit 1
fi
if [[ ! -d .git ]]; then
  echo "[AFB] Run this script from a Git clone of AFB-Immunefi-Scanner." >&2; exit 1
fi

BRANCH="$(git branch --show-current)"
if [[ -z "$BRANCH" ]]; then
  echo "[AFB] Detached HEAD: checkout the branch you want to update first." >&2; exit 1
fi
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "[AFB] Local tracked changes detected. Commit or stash them before updating." >&2
  exit 1
fi

echo "[AFB] Fetching latest origin/$BRANCH ..."
git fetch --prune origin
git pull --ff-only origin "$BRANCH"

echo "[AFB] Updating Python package and analysis dependencies ..."
if command -v python3 >/dev/null 2>&1; then
  python3 -m pip install --upgrade -e ".[analysis]"
else
  echo "[AFB] python3 is required." >&2; exit 1
fi

echo "[AFB] Checking optional tools ..."
for tool in slither forge aderyn echidna; do
  if command -v "$tool" >/dev/null 2>&1; then
    printf '  [OK] %s: %s\n' "$tool" "$(command -v "$tool")"
  else
    printf '  [--] %s not installed (optional for its analysis layer)\n' "$tool"
  fi
done

echo "[AFB] Update complete. Workspace, scopes and reports were not overwritten."
