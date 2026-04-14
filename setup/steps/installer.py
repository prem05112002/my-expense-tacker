"""
Dependency installer with async subprocess streaming.
Yields SSE-formatted lines for real-time terminal output in the browser.
"""
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent


def _venv_pip(venv_dir: Path) -> str:
    if sys.platform == "win32":
        return str(venv_dir / "Scripts" / "pip.exe")
    return str(venv_dir / "bin" / "pip")


def _venv_python(venv_dir: Path) -> str:
    if sys.platform == "win32":
        return str(venv_dir / "Scripts" / "python.exe")
    return str(venv_dir / "bin" / "python")


async def _stream_proc(args: list, cwd: Path):
    """Run a subprocess and yield its stdout/stderr line by line."""
    proc = await asyncio.create_subprocess_exec(
        *args,
        cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    async for raw in proc.stdout:
        line = raw.decode("utf-8", errors="replace").rstrip()
        if line:
            yield line
    await proc.wait()
    if proc.returncode != 0:
        raise RuntimeError(f"Command failed (exit {proc.returncode}): {' '.join(args)}")


async def stream_install(config: dict):
    """
    Generator that yields SSE lines driving the install step.
    Writes .env files, creates venvs, installs all deps.
    """
    from setup.steps.env_writer import write_env_files  # local import to avoid circular

    # --- Write .env files ---
    yield _sse("Writing configuration files...")
    result = write_env_files(config)
    if not result["ok"]:
        yield _sse_error(f"Failed to write config: {result['message']}")
        return
    yield _sse("  ✓ backend/.env written")
    yield _sse("  ✓ Etl/.env written")

    # --- Backend venv + pip install ---
    backend_dir = PROJECT_ROOT / "backend"
    backend_venv = backend_dir / "venv"

    yield _sse("\nSetting up backend virtual environment...")
    async for line in _stream_proc([sys.executable, "-m", "venv", str(backend_venv)], backend_dir):
        yield _sse(f"  {line}")
    yield _sse("  ✓ Backend venv ready")

    yield _sse("\nInstalling backend dependencies (this may take a few minutes)...")
    pip = _venv_pip(backend_venv)
    async for line in _stream_proc([pip, "install", "-r", "requirements.txt", "--quiet"], backend_dir):
        yield _sse(f"  {line}")
    yield _sse("  ✓ Backend dependencies installed")

    # --- ETL venv + pip install ---
    etl_dir = PROJECT_ROOT / "Etl"
    etl_venv = etl_dir / "venv"

    yield _sse("\nSetting up email pipeline virtual environment...")
    async for line in _stream_proc([sys.executable, "-m", "venv", str(etl_venv)], etl_dir):
        yield _sse(f"  {line}")
    yield _sse("  ✓ ETL venv ready")

    yield _sse("\nInstalling email pipeline dependencies...")
    pip = _venv_pip(etl_venv)
    async for line in _stream_proc([pip, "install", "-r", "requirements.txt", "--quiet"], etl_dir):
        yield _sse(f"  {line}")
    yield _sse("  ✓ ETL dependencies installed")

    # --- Frontend npm install ---
    frontend_dir = PROJECT_ROOT / "frontend"
    yield _sse("\nInstalling frontend dependencies...")
    npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
    async for line in _stream_proc([npm_cmd, "install"], frontend_dir):
        yield _sse(f"  {line}")
    yield _sse("  ✓ Frontend dependencies installed")

    # --- Mark setup complete ---
    (PROJECT_ROOT / ".setup_complete").write_text("1", encoding="utf-8")
    yield _sse("\n✓ All done! Setup complete.")
    yield _sse_done()


# ---------------------------------------------------------------------------
# SSE helpers
# ---------------------------------------------------------------------------

def _sse(text: str) -> str:
    return f"data: {text}\n\n"


def _sse_error(text: str) -> str:
    return f"event: error\ndata: {text}\n\n"


def _sse_done() -> str:
    return "event: done\ndata: {}\n\n"
