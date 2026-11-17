#!/usr/bin/env python3
"""
start_jarvis.py — One-Click Automated System Launcher
======================================================
Spawns the complete JARVIS ecosystem:
1. Fast local backend API server (FastAPI / Uvicorn on port 8080)
2. Interactive Electron Desktop HUD & Vite Frontend (port 5173)
3. Graceful shutdown handler for all child processes on Ctrl+C.
"""

import os
import sys
import time
import signal
import subprocess
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
VENV_PYTHON = ROOT_DIR / "venv" / "Scripts" / "python.exe"
APP_DIR = ROOT_DIR / "app"

if not VENV_PYTHON.exists():
    VENV_PYTHON = Path(sys.executable)


def main():
    print("===================================================================")
    print("        J.A.R.V.I.S — AUTOMATED SYSTEM LAUNCHER (V2.2)            ")
    print("===================================================================")
    print(f"[*] Root Directory : {ROOT_DIR}")
    print(f"[*] Python Runtime : {VENV_PYTHON}")

    processes = []

    try:
        # 1. Start the FastAPI backend server
        print("\n[1/2] Starting JARVIS Core API Server (Port 8080)...")
        api_cmd = [
            str(VENV_PYTHON),
            "-m",
            "uvicorn",
            "server.api_server:app",
            "--host",
            "0.0.0.0",
            "--port",
            "8080",
        ]
        api_proc = subprocess.Popen(api_cmd, cwd=str(ROOT_DIR))
        processes.append(("Backend API", api_proc))

        # Give API server a couple of seconds to bind
        time.sleep(2)

        # 2. Start Vite & Electron desktop HUD
        print("[2/2] Starting Electron Desktop HUD & Vite UI...")
        npm_cmd = ["cmd.exe", "/c", "npm", "run", "electron:dev"]
        electron_proc = subprocess.Popen(npm_cmd, cwd=str(APP_DIR))
        processes.append(("Desktop HUD", electron_proc))

        print("\n[✓] JARVIS Ecosystem is fully active.")
        print("[*] API Docs   : http://localhost:8080/docs")
        print("[*] Health     : http://localhost:8080/api/health")
        print("[*] Press Ctrl+C at any time to shut down all processes.\n")

        # Keep parent alive and monitor children
        while True:
            for name, proc in processes:
                ret = proc.poll()
                if ret is not None:
                    print(f"[!] Process '{name}' exited with return code {ret}.")
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n[*] Shutting down JARVIS processes...")
    finally:
        for name, proc in processes:
            if proc.poll() is None:
                print(f"[*] Terminating {name}...")
                try:
                    proc.terminate()
                    proc.wait(timeout=3)
                except Exception:
                    proc.kill()
        print("[✓] All processes safely halted. Good day, sir.")


if __name__ == "__main__":
    main()
