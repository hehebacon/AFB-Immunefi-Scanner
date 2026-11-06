"""Local tool discovery and Slither adapter."""
import shutil, subprocess
from pathlib import Path
TOOLS={"slither":["slither","--version"],"aderyn":["aderyn","--version"],"forge":["forge","--version"],"solc":["solc","--version"]}
def check_tools():
    results=[]
    for name,cmd in TOOLS.items():
        executable=shutil.which(cmd[0])
        if not executable: results.append({"name":name,"available":False,"path":None,"version":None}); continue
        try:
            p=subprocess.run([executable,*cmd[1:]],capture_output=True,text=True,timeout=8,check=False)
            version=(p.stdout or p.stderr).strip().splitlines()
            results.append({"name":name,"available":True,"path":executable,"version":version[0] if version else "unknown"})
        except (OSError,subprocess.TimeoutExpired) as exc: results.append({"name":name,"available":True,"path":executable,"version":f"check failed: {exc}"})
    return results
def run_aderyn_local(target:Path,output:Path,timeout:int=180):
    """Run Aderyn against a local project and preserve its native JSON report."""
    if not target.is_dir(): raise NotADirectoryError("Aderyn target must be a local project directory.")
    executable=shutil.which("aderyn")
    if not executable: raise FileNotFoundError("Aderyn is not installed.")
    output.parent.mkdir(parents=True,exist_ok=True)
    command=[executable,"--skip-update-check","--no-snippets","--output",str(output.resolve()),str(target.resolve())]
    proc=subprocess.run(command,capture_output=True,text=True,timeout=timeout,check=False)
    return {"command":command,"returncode":proc.returncode,"stdout":proc.stdout[-4000:],"stderr":proc.stderr[-4000:],"output":str(output.resolve()),"output_exists":output.is_file()}

def run_slither_local(target:Path,output:Path,timeout:int=180):
    """Run Slither against a local directory only; accepts no URL or address."""
    if not target.is_dir(): raise NotADirectoryError("Slither target must be a local source directory.")
    executable=shutil.which("slither")
    if not executable: raise FileNotFoundError("Slither is not installed.")
    output.parent.mkdir(parents=True,exist_ok=True)
    command=[executable,str(target.resolve()),"--json",str(output.resolve())]
    proc=subprocess.run(command,capture_output=True,text=True,timeout=timeout,check=False)
    return {"command":command,"returncode":proc.returncode,"stdout":proc.stdout[-4000:],"stderr":proc.stderr[-4000:],"output":str(output.resolve())}
