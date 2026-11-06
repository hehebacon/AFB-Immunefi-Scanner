"""Command-line interface for AFB Immunefi Scanner."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .workspace import initialize_workspace, workspace_status


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="afb-immunefi",
        description="Scope-first, local-first smart-contract research assistant.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    init_cmd = sub.add_parser("init", help="Create a structured research workspace.")
    init_cmd.add_argument("--workspace", type=Path, default=Path("./workspace"))

    status_cmd = sub.add_parser("status", help="Show workspace readiness.")
    status_cmd.add_argument("--workspace", type=Path, default=Path("./workspace"))

    return parser


def main() -> int:
    args = build_parser().parse_args()

    if args.command == "init":
        created = initialize_workspace(args.workspace)
        print(f"Workspace initialized: {args.workspace.resolve()}")
        for item in created:
            print(f"  + {item}")
        return 0

    if args.command == "status":
        status = workspace_status(args.workspace)
        print(json.dumps(status, indent=2))
        return 0

    return 2
