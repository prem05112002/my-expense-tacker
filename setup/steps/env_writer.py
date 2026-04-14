"""
Writes backend/.env and Etl/.env from collected wizard configuration.
"""
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent  # setup/steps/ -> setup/ -> project root


def write_env_files(config: dict) -> dict:
    """
    config keys expected:
      admin_pass, db_pass,
      imap_user, imap_password,
      llm_backend, llm_api_key
    """
    try:
        _write_backend_env(config)
        _write_etl_env(config)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "message": str(e)}


def _write_backend_env(config: dict) -> None:
    db_pass = config["db_pass"]
    imap_user = config["imap_user"]
    imap_pass = config["imap_password"]
    llm_backend = config.get("llm_backend", "GEMINI").upper()
    llm_key = config.get("llm_api_key", "")

    # Build LLM lines based on chosen provider
    if llm_backend == "GROQ":
        llm_lines = f"LLM_BACKEND=GROQ\nGROQ_API_KEY={llm_key}\nGEMINI_API_KEY=\n"
    else:
        llm_lines = f"LLM_BACKEND=GEMINI\nGEMINI_API_KEY={llm_key}\nGROQ_API_KEY=\n"

    content = (
        "# Database\n"
        "PG_ADMIN_USER=postgres\n"
        f"PG_ADMIN_PASS={config['admin_pass']}\n"
        "PG_HOST=localhost\n"
        "DB_NAME=expense_tracker\n"
        "DB_USER=tracker_user\n"
        f"DB_PASS={db_pass}\n"
        "\n"
        "# LLM\n"
        f"{llm_lines}"
        "\n"
        "# Email (IMAP)\n"
        "IMAP_SERVER=imap.gmail.com\n"
        f"IMAP_USER={imap_user}\n"
        f"IMAP_PASSWORD={imap_pass}\n"
        "MAIL_SERVER=imap.gmail.com\n"
    )

    env_path = PROJECT_ROOT / "backend" / ".env"
    env_path.write_text(content, encoding="utf-8")


def _write_etl_env(config: dict) -> None:
    db_pass = config["db_pass"]
    imap_user = config["imap_user"]
    imap_pass = config["imap_password"]

    content = (
        "# Email\n"
        "IMAP_SERVER=imap.gmail.com\n"
        f"IMAP_USER={imap_user}\n"
        f"IMAP_PASSWORD={imap_pass}\n"
        "MAIL_SERVER=imap.gmail.com\n"
        "\n"
        "# Database\n"
        "PG_ADMIN_USER=postgres\n"
        f"PG_ADMIN_PASS={config['admin_pass']}\n"
        "PG_HOST=localhost\n"
        "DB_NAME=expense_tracker\n"
        "DB_USER=tracker_user\n"
        f"DB_PASS={db_pass}\n"
        f"DATABASE_URL=postgresql://tracker_user:{db_pass}@localhost/expense_tracker\n"
    )

    env_path = PROJECT_ROOT / "Etl" / ".env"
    env_path.write_text(content, encoding="utf-8")
