#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SCOPES="${AFB_SCOPES_DIR:-$ROOT/scopes}"
POLL="${AFB_POLL_SECONDS:-3}"
mkdir -p "$SCOPES"

if ! command -v afb-immunefi >/dev/null 2>&1; then
  echo "[AFB] Install the project first: ./update.sh" >&2; exit 1
fi

echo "[AFB] Watching: $SCOPES"
echo "[AFB] Drop each authorized source tree into scopes/<name>/source/"
echo "[AFB] Each scope needs scopes/<name>/workspace/program/policy.yaml"
echo "[AFB] The policy must be human-reviewed and explicitly confirmed."

declare -A LAST_DIGEST=()
while true; do
  shopt -s nullglob
  for scope_dir in "$SCOPES"/*/; do
    name="$(basename "$scope_dir")"
    source_dir="${scope_dir%/}/source"
    workspace="${scope_dir%/}/workspace"
    policy="$workspace/program/policy.yaml"
    [[ -d "$source_dir" ]] || continue
    mapfile -t sol_files < <(find "$source_dir" -type f -name '*.sol' -print -quit)
    (("${#sol_files[@]}" > 0)) || continue

    if [[ ! -f "$policy" ]]; then
      echo "[AFB] WAIT $name: missing $policy (initialize workspace and review policy)."
      continue
    fi

    digest="$(find "$source_dir" -type f \( -name '*.sol' -o -name 'foundry.toml' -o -name 'hardhat.config.*' \) -print0 | sort -z | xargs -0 -r sha256sum | sha256sum | cut -d' ' -f1)"
    [[ "${LAST_DIGEST[$name]:-}" == "$digest" ]] && continue

    echo "[AFB] New/changed source detected: $name"
    if afb-immunefi analyze --source "$source_dir" --workspace "$workspace" --output "$workspace/findings/analysis.json"; then
      LAST_DIGEST[$name]="$digest"
      echo "[AFB] COMPLETE $name -> $workspace/findings/analysis.json"
      if ! grep -q '"potential_findings": 0' "$workspace/findings/analysis.json" 2>/dev/null; then
        :
      fi
      count="$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(len(d.get("findings", [])))' "$workspace/findings/analysis.json")"
      if [[ "$count" == "0" ]]; then
        echo "<no bugs more appear on this scope>"
        echo "[AFB] No enabled analyzer emitted a finding in this run. This is not proof of security."
      else
        echo "[AFB] $count unverified finding(s) need triage."
      fi
    else
      echo "[AFB] BLOCKED/FAILED $name. Check policy confirmation and analyzer logs."
    fi
  done
  sleep "$POLL"
done
