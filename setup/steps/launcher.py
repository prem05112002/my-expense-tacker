"""
Launches all application services and waits until they are ready.
"""
import asyncio
import sys
import time
from pathlib import Path

try:
    import urllib.request as _urllib
except ImportError:
    _urllib = None

PROJECT_ROOT = Path(__file__).parent.parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
FRONTEND_DIR = PROJECT_ROOT / "frontend"

# Ports used by the application services
BACKEND_PORT = 8000
FRONTEND_PORT = 5173

_procs: list = []  # track launched subprocesses for clean shutdown


def _venv_python(venv_dir: Path) -> str:
    if sys.platform == "win32":
        return str(venv_dir / "Scripts" / "python.exe")
    return str(venv_dir / "bin" / "python")


def launch_all() -> dict:
    """
    Start backend (uvicorn) and frontend (vite) as background processes.
    Returns {"ok": True} once both are detected as running.
    """
    try:
        _launch_backend()
        _launch_frontend()
        _wait_for_backend()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "message": str(e)}


def _launch_backend() -> None:
    venv_python = _venv_python(BACKEND_DIR / "venv")
    cmd = [
        venv_python, "-m", "uvicorn",
        "app.main:app",
        "--host", "127.0.0.1",
        "--port", str(BACKEND_PORT),
        "--reload",
    ]
    kwargs = _detach_kwargs()
    proc = _start_proc(cmd, BACKEND_DIR, **kwargs)
    _procs.append(proc)


def _launch_frontend() -> None:
    npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
    cmd = [npm_cmd, "run", "dev"]
    kwargs = _detach_kwargs()
    proc = _start_proc(cmd, FRONTEND_DIR, **kwargs)
    _procs.append(proc)


def _start_proc(cmd: list, cwd: Path, **kwargs):
    import subprocess
    return subprocess.Popen(cmd, cwd=str(cwd), **kwargs)


def _detach_kwargs() -> dict:
    """Return platform-specific kwargs so child processes outlive the wizard."""
    import subprocess
    if sys.platform == "win32":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def _wait_for_backend(timeout: int = 60) -> None:
    """Poll the backend health endpoint until it responds or we time out."""
    url = f"http://127.0.0.1:{BACKEND_PORT}/health"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with _urllib.urlopen(url, timeout=2) as resp:
                if resp.status == 200:
                    return
        except Exception:
            pass
        time.sleep(1)
    raise TimeoutError(
        f"Backend did not start within {timeout}s. "
        "Check that PostgreSQL is running and your credentials are correct."
    )


def stop_all() -> None:
    """Terminate all launched subprocesses (used on wizard shutdown if needed)."""
    for proc in _procs:
        try:
            proc.terminate()
        except Exception:
            pass
    _procs.clear()
