#!/usr/bin/env python3
"""JKLU University Information Agent - one command does everything.

    python run.py                 install missing packages -> collect data -> build index -> open the chatbot
    python run.py --cli           same, but chat in the terminal
    python run.py --eval          also run the evaluation (writes results/)
    python run.py --calibrate     evaluate + suggest evidence thresholds for your embedding model
    python run.py --offline       never touch the network (use cached/bundled data)
    python run.py --refresh       re-download PDFs even if cached
    python run.py --rebuild       force a rebuild of the vector index
    python run.py --skip-ingest   reuse existing data/processed/chunks.jsonl
    python run.py --no-ui         prepare everything, then exit
    python run.py --api           API + web UI without opening a browser (docs at /docs)
    python run.py --streamlit     use the Streamlit UI instead of the web UI
    python run.py --selftest      run the built-in test-suite

Every step is fault tolerant: if something optional is unavailable the pipeline
degrades gracefully instead of stopping.
"""
from __future__ import annotations

import argparse
import importlib
import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

if sys.version_info < (3, 9):
    sys.exit("Python 3.9 or newer is required.")

# import name -> pip name.  (required?, ...)
PACKAGES = {
    "requests": ("requests", True),
    "bs4": ("beautifulsoup4", True),
    "numpy": ("numpy", True),
    "pymupdf": ("PyMuPDF", True),
    "lxml": ("lxml", False),
    "faiss": ("faiss-cpu", False),
    "sklearn": ("scikit-learn", False),
    "sentence_transformers": ("sentence-transformers", False),
    "fastapi": ("fastapi", False),
    "uvicorn": ("uvicorn", False),
    "streamlit": ("streamlit", False),
}


def _importable(name: str) -> bool:
    try:
        importlib.import_module(name)
        return True
    except Exception:
        if name == "pymupdf":
            try:
                importlib.import_module("fitz")
                return True
            except Exception:
                return False
        return False


def _pip(args: list[str]) -> bool:
    cmd = [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "-q", *args]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 and "externally-managed" in (r.stderr or "").lower():
        r = subprocess.run(cmd + ["--break-system-packages"], capture_output=True, text=True)
    return r.returncode == 0


def ensure_packages() -> None:
    missing = [n for n in PACKAGES if not _importable(n)]
    if not missing or os.environ.get("JKLU_NO_AUTOINSTALL"):
        missing = [n for n in missing if PACKAGES[n][1]]
        if not missing:
            return
    print(f"[setup] installing missing packages: {', '.join(PACKAGES[m][0] for m in missing)}")
    if not _pip([PACKAGES[m][0] for m in missing]):          # bulk failed -> one by one
        for m in missing:
            if not _importable(m):
                ok = _pip([PACKAGES[m][0]])
                if not ok:
                    print(f"[setup] could not install {PACKAGES[m][0]} "
                          f"({'REQUIRED' if PACKAGES[m][1] else 'optional - a fallback will be used'})")
    importlib.invalidate_caches()
    for n, (pip_name, required) in PACKAGES.items():
        if required and not _importable(n):
            sys.exit(f"\n[setup] Required package '{pip_name}' is missing. Run:  pip install -r requirements.txt")


def free_port(preferred: int) -> int:
    for port in [preferred] + list(range(preferred + 1, preferred + 30)):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.3)
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return preferred


def banner(text: str) -> None:
    print("\n" + "=" * 72 + f"\n  {text}\n" + "=" * 72)


def run_cli(agent) -> None:
    banner("JKLU Assistant (terminal) - type 'exit' to quit")
    history: list[dict] = []
    while True:
        try:
            q = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if q.lower() in ("exit", "quit", "q"):
            return
        if not q:
            continue
        r = agent.ask(q, history=history)
        print(f"\n[{r['status'].upper()}  confidence={r['confidence']:.2f}  {r['latency_ms']} ms]")
        print(r["answer"])
        for s in r["sources"]:
            pg = f" p.{s['page']}" if s.get("page") else ""
            print(f"   [{s['n']}] {s['title']}{pg} - {s['url']}")
        history += [{"role": "user", "content": q}, {"role": "assistant", "content": r["answer"]}]
        history = history[-8:]


def start_api(port: int):
    import uvicorn
    from jklu.api import app
    server = uvicorn.Server(uvicorn.Config(app, host=os.environ.get("JKLU_API_HOST", "127.0.0.1"),
                                           port=port, log_level="warning"))
    server.install_signal_handlers = lambda: None            # running in a thread
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    return server, t


def wait_for(url: str, seconds: int = 120) -> bool:
    import requests
    end = time.time() + seconds
    while time.time() < end:
        try:
            if requests.get(url, timeout=2).status_code == 200:
                return True
        except Exception:
            time.sleep(0.5)
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description="JKLU University Information Agent")
    ap.add_argument("--offline", action="store_true", help="do not use the network")
    ap.add_argument("--refresh", action="store_true", help="re-download cached PDFs")
    ap.add_argument("--rebuild", action="store_true", help="force rebuilding the vector index")
    ap.add_argument("--skip-ingest", action="store_true", help="reuse existing chunks.jsonl")
    ap.add_argument("--eval", action="store_true", help="run the evaluation after building")
    ap.add_argument("--calibrate", action="store_true", help="tune evidence thresholds on the test set")
    ap.add_argument("--cli", action="store_true", help="chat in the terminal")
    ap.add_argument("--api", action="store_true", help="API only")
    ap.add_argument("--no-ui", action="store_true", help="prepare data/index and exit")
    ap.add_argument("--streamlit", action="store_true", help="use the Streamlit UI instead of the web UI")
    ap.add_argument("--campus", action="store_true", help="ingest external campus documents and rebuild index")
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.campus:
        args.rebuild = True
        args.offline = True


    banner("JKLU University Information Agent")
    ensure_packages()

    from jklu import config as C
    from jklu.utils import log

    if args.selftest:
        import unittest
        suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
        return 0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1

    # ---- Phase 1: data ---------------------------------------------------------
    if args.skip_ingest and C.CHUNKS_PATH.is_file():
        log.info("Skipping ingestion (using %s)", C.CHUNKS_PATH.relative_to(ROOT))
    else:
        banner("Phase 1 - collect, clean, chunk")
        from jklu.ingest import run_ingestion
        summary = run_ingestion(offline=args.offline, refresh=args.refresh)
        for cat, n in summary["chunks_per_category"].items():
            print(f"   {cat:<13}{n:>6} chunks")
        if summary["chunks"] == 0:
            print("No data could be collected. Connect to the internet and run again.")
            return 1

    # ---- Phase 2: index --------------------------------------------------------
    banner("Phase 2 - embeddings + FAISS index")
    from jklu.index import ensure_index
    ensure_index(force=args.rebuild)

    if args.eval or args.calibrate:
        banner("Evaluation")
        from jklu.evaluate import evaluate
        res = evaluate(calibrate=args.calibrate)
        if res.get('calibration'):
            print('Suggested settings for .env:', res['calibration']['suggested_env'])
        print(f"Report written to {C.RESULTS_DIR.relative_to(ROOT)}/evaluation_report.md")

    if args.no_ui:
        print("\nAll set. Start the chatbot any time with:  python run.py --skip-ingest")
        return 0

    # ---- Phase 3: serve ----------------------------------------------------------
    if args.cli:
        from jklu.agent import JKLUAgent
        run_cli(JKLUAgent())
        return 0

    api_port = free_port(C.API_PORT)
    banner("Starting the API")
    start_api(api_port)
    api_url = f"http://127.0.0.1:{api_port}"
    if not wait_for(f"{api_url}/health", 180):
        print("API did not start - falling back to the terminal chat.")
        from jklu.agent import JKLUAgent
        run_cli(JKLUAgent())
        return 0
    print(f"API ready:  {api_url}/docs")
    if args.api:
        print("Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            return 0

    if not args.streamlit:                                  # default: the web UI served by the API
        banner(f"Chatbot UI: {api_url}   (Ctrl+C to stop)")
        if not args.no_browser:
            threading.Timer(1.5, lambda: webbrowser.open(api_url)).start()
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            return 0

    if not _importable("streamlit"):
        print("Streamlit is not installed - using the terminal chat instead.")
        from jklu.agent import JKLUAgent
        run_cli(JKLUAgent())
        return 0

    ui_port = free_port(C.UI_PORT)
    banner(f"Chatbot UI: http://localhost:{ui_port}   (Ctrl+C to stop)")
    env = {**os.environ, "JKLU_API_URL": api_url, "PYTHONPATH": str(ROOT)}
    proc = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", str(ROOT / "frontend" / "app.py"),
         "--server.port", str(ui_port), "--server.headless", "true",
         "--browser.gatherUsageStats", "false"], env=env)
    if not args.no_browser:
        threading.Timer(3.0, lambda: webbrowser.open(f"http://localhost:{ui_port}")).start()
    try:
        proc.wait()
    except KeyboardInterrupt:
        pass
    finally:
        if proc.poll() is None:
            proc.terminate()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nStopped.")
        sys.exit(0)










# 1. Navigate to the project root directory:
# cd "c:\Users\Nikunj katta\Downloads\JKLU_Project (1)\JKLU_Project"

# 2. Run the application using the project virtual environment (skipping redundant re-ingestion):
# .\.venv\Scripts\python.exe run.py --skip-ingest