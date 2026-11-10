"""Local tool discovery and adapters for Solidity analyzers and fuzzers."""
import json
import re
import shutil
import subprocess
from pathlib import Path

TOOLS = {
    "slither": ["slither", "--version"],
    "aderyn": ["aderyn", "--version"],
    "echidna": ["echidna", "--version"],
    "forge": ["forge", "--version"],
    "solc": ["solc", "--version"],
}


def check_tools():
    results = []
    for name, cmd in TOOLS.items():
        executable = shutil.which(cmd[0])
        if not executable:
            results.append({"name": name, "available": False, "path": None, "version": None})
            continue
        try:
            proc = subprocess.run(
                [executable, *cmd[1:]],
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
            )
            version = (proc.stdout or proc.stderr).strip().splitlines()
            results.append({
                "name": name,
                "available": True,
                "path": executable,
                "version": version[0] if version else "unknown",
            })
        except (OSError, subprocess.TimeoutExpired) as exc:
            results.append({
                "name": name,
                "available": True,
                "path": executable,
                "version": f"check failed: {exc}",
            })
    return results


def run_aderyn_local(target: Path, output: Path, timeout: int = 180):
    """Run Aderyn against a local project and preserve its native report."""
    if not target.is_dir():
        raise NotADirectoryError("Aderyn target must be a local project directory.")
    executable = shutil.which("aderyn")
    if not executable:
        raise FileNotFoundError("Aderyn is not installed.")
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        executable, ".", "-o", str(output.resolve()),
        "--no-snippets", "--skip-update-check",
    ]
    proc = subprocess.run(
        command, cwd=target.resolve(), capture_output=True,
        text=True, timeout=timeout, check=False,
    )
    return {
        "command": command,
        "returncode": proc.returncode,
        "stdout": proc.stdout[-4000:],
        "stderr": proc.stderr[-4000:],
        "output": str(output.resolve()),
        "output_exists": output.is_file(),
    }


def run_slither_local(target: Path, output: Path, timeout: int = 180):
    """Run Slither against a local source directory only; accepts no URL or address."""
    if not target.is_dir():
        raise NotADirectoryError("Slither target must be a local source directory.")
    executable = shutil.which("slither")
    if not executable:
        raise FileNotFoundError("Slither is not installed.")
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [executable, str(target.resolve()), "--json", str(output.resolve())]
    proc = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    return {
        "command": command,
        "returncode": proc.returncode,
        "stdout": proc.stdout[-4000:],
        "stderr": proc.stderr[-4000:],
        "output": str(output.resolve()),
    }


def run_echidna_local(
    target: Path,
    contract: str,
    output: Path,
    *,
    config: Path | None = None,
    test_limit: int = 5000,
    seq_len: int = 50,
    timeout: int = 1800,
):
    """Run Echidna property fuzzing against a local harness and save its JSON campaign."""
    if not target.is_dir():
        raise NotADirectoryError("Echidna target must be a local project directory.")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", contract or ""):
        raise ValueError("Contract must be a Solidity identifier.")
    if not 1 <= test_limit <= 1_000_000:
        raise ValueError("test_limit must be between 1 and 1,000,000.")
    if not 1 <= seq_len <= 10_000:
        raise ValueError("seq_len must be between 1 and 10,000.")
    if timeout < 1:
        raise ValueError("timeout must be positive.")

    executable = shutil.which("echidna")
    if not executable:
        raise FileNotFoundError("Echidna is not installed.")
    if config is not None and not config.is_file():
        raise FileNotFoundError(f"Echidna config does not exist: {config}")

    output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        executable,
        ".",
        "--contract", contract,
        "--test-mode", "property",
        "--test-limit", str(test_limit),
        "--seq-len", str(seq_len),
        "--format", "json",
    ]
    if config is not None:
        command.extend(["--config", str(config.resolve())])

    proc = subprocess.run(
        command,
        cwd=target.resolve(),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    raw_output = proc.stdout.strip()
    parsed = None
    parse_error = None
    if raw_output:
        try:
            parsed = json.loads(raw_output)
        except json.JSONDecodeError as exc:
            parse_error = str(exc)
    output.write_text(
        json.dumps(parsed, indent=2) if parsed is not None else raw_output,
        encoding="utf-8",
    )
    return {
        "command": command,
        "returncode": proc.returncode,
        "output": str(output.resolve()),
        "output_exists": output.is_file(),
        "json_parsed": parsed is not None,
        "campaign_success": parsed.get("success") if isinstance(parsed, dict) else None,
        "stdout": proc.stdout[-4000:],
        "stderr": proc.stderr[-4000:],
        "parse_error": parse_error,
        "note": "A falsified property is a local test counterexample requiring triage; it is not automatically a reportable vulnerability.",
    }
