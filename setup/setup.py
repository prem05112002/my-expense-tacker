"""
Expense Tracker — Setup Entry Point
====================================
Usage:
  python setup/setup.py            # Full setup wizard
  python setup/setup.py --launch   # Skip wizard, just launch services (after first setup)

What this script does:
  1. Bootstraps its own minimal dependencies (fastapi, uvicorn, psycopg2-binary)
  2. Starts the wizard web server on port 3001
  3. Opens the browser to localhost:3001
  4. Keeps running until the user presses Ctrl+C
"""
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

# ---------------------------------------------------------------------------
# Fix asyncio on Windows (must happen before any async import)
# ---------------------------------------------------------------------------
if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SETUP_DIR = Path(__file__).parent
PROJECT_ROOT = SETUP_DIR.parent
WIZARD_SERVER = SETUP_DIR / "server.py"
COMPLETE_MARKER = PROJECT_ROOT / ".setup_complete"

WIZARD_PORT = 3001

# ---------------------------------------------------------------------------
# Minimal deps needed to run the wizard server
# ---------------------------------------------------------------------------
BOOTSTRAP_DEPS = [
    "fastapi",
    "uvicorn[standard]",
    "psycopg2-binary",
    "python-dotenv",
]


def _bootstrap_deps() -> None:
    """Silently install wizard server dependencies if not already present."""
    print("Checking setup dependencies...")
    try:
        import fastapi  # noqa: F401
        import uvicorn  # noqa: F401
        import psycopg2  # noqa: F401
        print("  All dependencies ready.")
    except ImportError:
        print("  Installing required packages (one-time)...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--quiet", *BOOTSTRAP_DEPS],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        print("  Done.")


def _is_launch_only() -> bool:
    return "--launch" in sys.argv


def _open_browser_delayed(url: str, delay: float = 1.5) -> None:
    """Open browser after a short delay so the server has time to start."""
    time.sleep(delay)
    webbrowser.open(url)


def main() -> None:
    launch_only = _is_launch_only()

    if launch_only and not COMPLETE_MARKER.exists():
        print(
            "Setup has not been completed yet.\n"
            "Please run: python setup/setup.py\n"
            "to go through the setup wizard first."
        )
        sys.exit(1)

    _bootstrap_deps()

    url = f"http://localhost:{WIZARD_PORT}"
    if launch_only:
        url += "?launch=1"

    print(f"\nStarting setup wizard at {url}")
    print("A browser window will open automatically.")
    print("Press Ctrl+C to stop.\n")

    # Open browser in a background thread after a short delay
    import threading
    t = threading.Thread(target=_open_browser_delayed, args=(url,), daemon=True)
    t.start()

    # Start the wizard server (blocking)
    server_module = "setup.server:app"  # when run from project root

    # Adjust sys.path so imports inside setup/ resolve correctly
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    try:
        import uvicorn
        uvicorn.run(
            server_module,
            host="127.0.0.1",
            port=WIZARD_PORT,
            reload=False,
            log_level="warning",  # keep terminal clean
        )
    except KeyboardInterrupt:
        print("\nSetup wizard stopped.")


if __name__ == "__main__":
    main()
