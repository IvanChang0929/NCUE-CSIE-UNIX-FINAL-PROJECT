import os
import sys
import time
import signal
import subprocess
import atexit
from pathlib import Path

ROOT = Path(__file__).resolve().parent

processes = []


def start_process(name, cmd):
    print(f"[Launcher] Starting {name}...")
    print(f"[Launcher] Command: {' '.join(cmd)}")

    p = subprocess.Popen(
        cmd,
        cwd=ROOT,
        preexec_fn=os.setsid
    )

    processes.append((name, p))
    return p


def stop_all():
    print("\n[Launcher] Stopping all services...")

    for name, p in reversed(processes):
        if p.poll() is None:
            print(f"[Launcher] Stopping {name}...")
            try:
                os.killpg(os.getpgid(p.pid), signal.SIGTERM)
            except ProcessLookupError:
                pass

    time.sleep(1)

    for name, p in reversed(processes):
        if p.poll() is None:
            print(f"[Launcher] Force killing {name}...")
            try:
                os.killpg(os.getpgid(p.pid), signal.SIGKILL)
            except ProcessLookupError:
                pass


def handle_signal(signum, frame):
    stop_all()
    sys.exit(0)


def main():
    atexit.register(stop_all)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    # 1. 啟動 FastAPI backend
    start_process(
        "Backend",
        [
            sys.executable,
            "-m",
            "uvicorn",
            "backend.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
        ]
    )

    # 給 backend 一點時間起來
    time.sleep(2)

    # 2. 啟動 worker
    start_process(
        "Worker",
        [
            sys.executable,
            "sandbox/worker.py"
        ]
    )

    # 3. 啟動 UI
    # 這行要改成你真正的 UI 檔案
    ui = start_process(
        "UI",
        [
            sys.executable,
            "frontend/ui.py"
        ]
    )

    # UI 關掉後，launcher 就結束，順便關 backend / worker
    ui.wait()


if __name__ == "__main__":
    main()