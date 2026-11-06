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
def run_slither_local(target:Path,output:Path,timeout:int=180):
    """Run Slither against a local directory only; accepts no URL or address."""
    if not target.is_dir(): raise NotADirectoryError("Slither target must be a local source directory.")
    executable=shutil.which("slither")
    if not executable: raise FileNotFoundError("Slither is not installed.")
    output.parent.mkdir(parents=True,exist_ok=True)
    command=[executable,str(target.resolve()),"--json",str(output.resolve())]
    proc=subprocess.run(command,capture_output=True,text=True,timeout=timeout,check=False)
    return {"command":command,"returncode":proc.returncode,"stdout":proc.stdout[-4000:],"stderr":proc.stderr[-4000:],"output":str(output.resolve())}
