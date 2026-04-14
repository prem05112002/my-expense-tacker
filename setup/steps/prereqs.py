"""
Prerequisite checker: verifies Python, Node.js, and PostgreSQL versions.
"""
import re
import shutil
import subprocess
import sys


def check_prereqs() -> dict:
    return {
        "python": _check_python(),
        "node": _check_node(),
        "postgres": _check_postgres(),
    }


def _check_python() -> dict:
    v = sys.version_info
    found = f"{v.major}.{v.minor}.{v.micro}"
    ok = v >= (3, 10)
    return {
        "name": "Python 3.10+",
        "ok": ok,
        "found": found,
        "download": "https://www.python.org/downloads/",
        "instruction": "Download and install Python 3.10 or newer, then re-check.",
    }


def _check_node() -> dict:
    path = shutil.which("node")
    if not path:
        return {
            "name": "Node.js 18+",
            "ok": False,
            "found": None,
            "download": "https://nodejs.org/en/download",
            "instruction": "Download and install Node.js 18 LTS, then re-check.",
        }
    try:
        result = subprocess.run(
            ["node", "--version"], capture_output=True, text=True, timeout=10
        )
        raw = result.stdout.strip().lstrip("v")
        major = int(raw.split(".")[0])
        return {
            "name": "Node.js 18+",
            "ok": major >= 18,
            "found": raw,
            "download": "https://nodejs.org/en/download",
            "instruction": "Please upgrade to Node.js 18 or newer.",
        }
    except Exception as e:
        return {
            "name": "Node.js 18+",
            "ok": False,
            "found": None,
            "download": "https://nodejs.org/en/download",
            "instruction": f"Could not read Node.js version: {e}",
        }


def _check_postgres() -> dict:
    path = shutil.which("psql") or shutil.which("pg_isready")
    if not path:
        return {
            "name": "PostgreSQL 14+",
            "ok": False,
            "found": None,
            "download": "https://www.postgresql.org/download/",
            "instruction": (
                "Download and install PostgreSQL 14 or newer. "
                "Make sure to remember the admin password you set during installation."
            ),
        }
    try:
        result = subprocess.run(
            ["psql", "--version"], capture_output=True, text=True, timeout=10
        )
        text = result.stdout.strip() or result.stderr.strip()
        match = re.search(r"(\d+)\.(\d+)", text)
        if match:
            major = int(match.group(1))
            found = f"{match.group(1)}.{match.group(2)}"
        else:
            major, found = 0, "unknown"
        return {
            "name": "PostgreSQL 14+",
            "ok": major >= 14,
            "found": found,
            "download": "https://www.postgresql.org/download/",
            "instruction": "Please upgrade to PostgreSQL 14 or newer.",
        }
    except Exception as e:
        return {
            "name": "PostgreSQL 14+",
            "ok": False,
            "found": None,
            "download": "https://www.postgresql.org/download/",
            "instruction": f"Could not read PostgreSQL version: {e}",
        }
