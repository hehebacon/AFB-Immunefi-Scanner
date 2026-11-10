"""Desktop UI for AFB Immunefi Scanner.

The UI is intentionally a thin front-end over the existing local analysis engine.
It does not implement a second scanner or contact deployed targets.
"""
from __future__ import annotations

import json
import queue
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .analysis import run_analysis
from .policy import require_policy
from .workspace import initialize_workspace

APP_TITLE = "AFB | Smart Contract Logic Scanner"


class AFBApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1120x760")
        self.root.minsize(900, 620)
        self.root.configure(bg="#10141d")
        self.events: queue.Queue = queue.Queue()
        self.busy = False

        self.source_var = tk.StringVar()
        self.workspace_var = tk.StringVar(value=str(Path.cwd() / "afb-workspace"))
        self.status_var = tk.StringVar(value="Ready · Select a local Solidity source folder")
        self.static_var = tk.BooleanVar(value=True)

        self._style()
        self._build()
        self.root.after(150, self._poll_events)

    def _style(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background="#10141d")
        style.configure("Panel.TFrame", background="#171e2b")
        style.configure("TLabel", background="#10141d", foreground="#e8edf7", font=("DejaVu Sans", 10))
        style.configure("Muted.TLabel", background="#10141d", foreground="#93a0b5", font=("DejaVu Sans", 9))
        style.configure("Panel.TLabel", background="#171e2b", foreground="#e8edf7", font=("DejaVu Sans", 10))
        style.configure("Title.TLabel", background="#10141d", foreground="#f4f7ff", font=("DejaVu Sans", 22, "bold"))
        style.configure("Section.TLabel", background="#171e2b", foreground="#75a7ff", font=("DejaVu Sans", 11, "bold"))
        style.configure("TButton", font=("DejaVu Sans", 9, "bold"), padding=(12, 8))
        style.configure("Accent.TButton", background="#2864d7", foreground="white")
        style.map("Accent.TButton", background=[("disabled", "#39465d"), ("active", "#3978ed")])
        style.configure("Horizontal.TProgressbar", troughcolor="#252f40", background="#4d8cff")

    def _build(self):
        outer = ttk.Frame(self.root, padding=22)
        outer.pack(fill="both", expand=True)

        header = ttk.Frame(outer)
        header.pack(fill="x", pady=(0, 18))
        ttk.Label(header, text="AFB", style="Title.TLabel").pack(side="left")
        ttk.Label(header, text="  SMART CONTRACT ANALYSIS", style="Muted.TLabel").pack(side="left", padx=(10, 0), pady=(12, 0))
        ttk.Label(header, text="LOCAL SOURCE ONLY", style="Muted.TLabel").pack(side="right", pady=(12, 0))

        scope = ttk.Frame(outer, style="Panel.TFrame", padding=16)
        scope.pack(fill="x", pady=(0, 14))
        ttk.Label(scope, text="01  ·  SCOPE", style="Section.TLabel").pack(anchor="w", pady=(0, 12))

        ttk.Label(scope, text="Solidity source folder", style="Panel.TLabel").pack(anchor="w")
        row = ttk.Frame(scope, style="Panel.TFrame")
        row.pack(fill="x", pady=(5, 12))
        self.source_entry = ttk.Entry(row, textvariable=self.source_var)
        self.source_entry.pack(side="left", fill="x", expand=True, ipady=6)
        ttk.Button(row, text="Browse", command=self._choose_source).pack(side="left", padx=(8, 0))

        ttk.Label(scope, text="Analysis workspace", style="Panel.TLabel").pack(anchor="w")
        row2 = ttk.Frame(scope, style="Panel.TFrame")
        row2.pack(fill="x", pady=(5, 10))
        ttk.Entry(row2, textvariable=self.workspace_var).pack(side="left", fill="x", expand=True, ipady=6)
        ttk.Button(row2, text="Choose", command=self._choose_workspace).pack(side="left", padx=(8, 0))

        actions = ttk.Frame(scope, style="Panel.TFrame")
        actions.pack(fill="x", pady=(3, 0))
        ttk.Button(actions, text="Initialize Workspace", command=self._initialize).pack(side="left")
        ttk.Button(actions, text="Open Scope Policy", command=self._open_policy).pack(side="left", padx=8)
        ttk.Checkbutton(actions, text="Run available static tools (Slither / Aderyn)", variable=self.static_var).pack(side="right")

        run_panel = ttk.Frame(outer, style="Panel.TFrame", padding=16)
        run_panel.pack(fill="x", pady=(0, 14))
        ttk.Label(run_panel, text="02  ·  ANALYSIS", style="Section.TLabel").pack(anchor="w", pady=(0, 10))
        runrow = ttk.Frame(run_panel, style="Panel.TFrame")
        runrow.pack(fill="x")
        self.start_button = ttk.Button(runrow, text="▶  START SCAN", style="Accent.TButton", command=self._start_scan)
        self.start_button.pack(side="left")
        self.progress = ttk.Progressbar(runrow, mode="indeterminate", length=260)
        self.progress.pack(side="left", padx=14, fill="x", expand=True)
        ttk.Label(run_panel, textvariable=self.status_var, style="Panel.TLabel").pack(anchor="w", pady=(10, 0))

        results = ttk.Frame(outer, style="Panel.TFrame", padding=16)
        results.pack(fill="both", expand=True)
        top = ttk.Frame(results, style="Panel.TFrame")
        top.pack(fill="x", pady=(0, 10))
        ttk.Label(top, text="03  ·  FINDINGS", style="Section.TLabel").pack(side="left")
        self.summary_var = tk.StringVar(value="No scan has been run yet")
        ttk.Label(top, textvariable=self.summary_var, style="Panel.TLabel").pack(side="right")

        columns = ("severity", "analyzer", "title", "location", "status")
        self.table = ttk.Treeview(results, columns=columns, show="headings", height=12)
        for key, label, width in [
            ("severity", "SEVERITY", 95), ("analyzer", "ANALYZER", 115),
            ("title", "FINDING / REVIEW LEAD", 390), ("location", "SOURCE", 250),
            ("status", "STATUS", 150)
        ]:
            self.table.heading(key, text=label)
            self.table.column(key, width=width, anchor="w")
        self.table.pack(fill="both", expand=True)

        footer = ttk.Frame(results, style="Panel.TFrame")
        footer.pack(fill="x", pady=(10, 0))
        ttk.Button(footer, text="Open Report Folder", command=self._open_reports).pack(side="left")
        ttk.Label(footer, text="All generated findings are unverified until manually validated.", style="Muted.TLabel").pack(side="right")

    def _choose_source(self):
        path = filedialog.askdirectory(title="Choose local Solidity source folder")
        if path:
            self.source_var.set(path)
            if not self.workspace_var.get().strip():
                self.workspace_var.set(str(Path(path).parent / "afb-workspace"))

    def _choose_workspace(self):
        path = filedialog.askdirectory(title="Choose AFB workspace")
        if path:
            self.workspace_var.set(path)

    def _paths(self):
        source = Path(self.source_var.get()).expanduser().resolve()
        workspace = Path(self.workspace_var.get()).expanduser().resolve()
        return source, workspace

    def _initialize(self):
        try:
            _, workspace = self._paths()
            created = initialize_workspace(workspace)
            policy = workspace / "program" / "policy.yaml"
            self.status_var.set(f"Workspace ready · {len(created)} template item(s) created")
            messagebox.showinfo(
                "Workspace initialized",
                f"Workspace created at:\n{workspace}\n\nReview and complete this policy file before scanning:\n{policy}"
            )
            self._open_path(policy)
        except Exception as exc:
            messagebox.showerror("Workspace error", str(exc))

    def _open_path(self, path: Path):
        try:
            if not path.exists():
                raise FileNotFoundError(path)
            subprocess.Popen(["xdg-open", str(path)])
        except Exception as exc:
            messagebox.showerror("Open error", f"Could not open {path}: {exc}")

    def _open_policy(self):
        _, workspace = self._paths()
        self._open_path(workspace / "program" / "policy.yaml")

    def _open_reports(self):
        _, workspace = self._paths()
        folder = workspace / "findings"
        folder.mkdir(parents=True, exist_ok=True)
        self._open_path(folder)

    def _start_scan(self):
        if self.busy:
            return
        try:
            source, workspace = self._paths()
            if not source.is_dir():
                raise ValueError("Choose an existing local source folder first.")
            if not any(source.rglob("*.sol")):
                raise ValueError("The selected folder contains no Solidity (.sol) files.")
            policy_path = workspace / "program" / "policy.yaml"
            require_policy(policy_path)
        except Exception as exc:
            messagebox.showwarning("Scope / policy gate", f"Scan not started.\n\n{exc}\n\nReview the official program scope and complete the workspace policy first.")
            return

        self.busy = True
        self.start_button.configure(state="disabled")
        self.progress.start(12)
        self.status_var.set("Scanning local source · running enabled analysis layers…")
        self.summary_var.set("Analysis in progress")
        for item in self.table.get_children():
            self.table.delete(item)

        output = workspace / "findings" / "analysis.json"
        thread = threading.Thread(
            target=self._scan_worker,
            args=(source, workspace, output, self.static_var.get()),
            daemon=True,
        )
        thread.start()

    def _scan_worker(self, source: Path, workspace: Path, output: Path, include_static: bool):
        try:
            result = run_analysis(source, workspace, include_static_tools=include_static)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(result, indent=2), encoding="utf-8")
            self.events.put(("complete", result, output))
        except Exception as exc:
            self.events.put(("error", str(exc), None))

    def _poll_events(self):
        try:
            while True:
                event, payload, output = self.events.get_nowait()
                self.progress.stop()
                self.busy = False
                self.start_button.configure(state="normal")
                if event == "error":
                    self.status_var.set("Scan failed")
                    messagebox.showerror("Scan failed", payload)
                    continue

                findings = payload.get("findings", [])
                coverage = payload.get("coverage", {})
                for finding in findings:
                    location = finding.get("source", "")
                    if finding.get("line"):
                        location += f":{finding['line']}"
                    self.table.insert("", "end", values=(
                        finding.get("severity", "unknown"),
                        finding.get("analyzer", finding.get("category", "AFB")),
                        finding.get("title", "Untitled"),
                        location,
                        finding.get("status", "unverified"),
                    ))
                count = len(findings)
                self.summary_var.set(f"{count} finding(s) · {coverage.get('solidity_files', 0)} Solidity file(s)")
                tools = coverage.get("tools", {})
                self.status_var.set(f"Completed · report: {output}")
                if count == 0:
                    messagebox.showinfo(
                        "Scan complete",
                        "<no bugs more appear on this scope>\n\nNo enabled analyzer emitted a finding in this run. This is not proof that the source is secure."
                    )
                else:
                    messagebox.showinfo("Scan complete", f"Analysis finished with {count} unverified finding(s).\n\nReport: {output}")
        except queue.Empty:
            pass
        self.root.after(150, self._poll_events)


def main():
    root = tk.Tk()
    AFBApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
