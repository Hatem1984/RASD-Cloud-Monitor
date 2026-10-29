"""One-click owner-local MA'AL competition workspace launcher.

Reuses the existing single V0.3 UI and pinned llama.cpp binary. Does not fetch,
install, update, expose a network server, email, or change production state.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.request import urlopen
from urllib.error import URLError
import webbrowser

HERE=Path(__file__).resolve().parent
PROJECT=next((p for p in HERE.parents if p.name.upper()=="MAAL"),None)
if PROJECT is None: raise RuntimeError("missing_maal_project_root")
BIN=PROJECT/"07_LOCAL_TOOL_CACHE"/"ai_inference"/"llama.cpp"/"llama-server.exe"
MODEL=PROJECT/"07_LOCAL_TOOL_CACHE"/"ai_inference"/"models"/"Qwen3-1.7B-Q4_K_M.gguf"
WORK=PROJECT/"04_HISTORICAL_QA"/"MAAL_COMPETITION_MVP_20261028"
URL="http://127.0.0.1:52344/"


def get_json(endpoint):
    try:
        with urlopen(endpoint,timeout=2) as f: return json.load(f)
    except (OSError,URLError,ValueError,TimeoutError): return None


def agent_ready():
    item=get_json(URL+"api/agent-journey")
    return (isinstance(item,dict) and
            item.get("schema")=="MAAL_COMPETITION_JOURNEY_V1" and
            item.get("live_signal") is False and
            item.get("operations",{}).get("external_actions") is False)


def model_ready():
    data=get_json("http://127.0.0.1:8088/health")
    return (isinstance(data,dict) and
            data.get("status") in ("ok","ready","healthy"))


def start_daemon(args,log_name):
    logs=WORK/"runtime_logs"
    logs.mkdir(parents=True,exist_ok=True)
    f=open(logs/log_name,"ab",buffering=0)
    try:
        subprocess.Popen(args,stdin=subprocess.DEVNULL,stdout=f,stderr=f,
                         cwd=str(HERE.parent),
                         creationflags=(getattr(subprocess,"CREATE_NEW_PROCESS_GROUP",0)
                                        |getattr(subprocess,"DETACHED_PROCESS",0)))
    finally: f.close()


def wait_for(fn,seconds=30):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        if fn(): return True
        time.sleep(.4)
    return False


def main():
    if sys.platform!="win32":
        raise RuntimeError("launcher_windows_only")
    if not (BIN.is_file() and MODEL.is_file()):
        raise RuntimeError("pinned_local_llama_cpp_or_model_missing")
    if not model_ready():
        start_daemon([str(BIN),"-m",str(MODEL),"--host","127.0.0.1",
                      "--port","8088","-c","4096","-t","8"],"qwen3.log")
        if not wait_for(model_ready,45):
            raise RuntimeError("local_qwen3_did_not_become_ready")
    if not agent_ready():
        start_daemon([sys.executable,"-B","-X","utf8",str(HERE/"server.py"),"52344"],
                     "local_v03_server.log")
        if not wait_for(agent_ready,20):
            raise RuntimeError("local_agent_server_did_not_become_ready")
    print("MAAL_COMPETITION_LOCAL_WORKSPACE_READY",URL)
    webbrowser.open(URL)


if __name__=="__main__":
    main()
