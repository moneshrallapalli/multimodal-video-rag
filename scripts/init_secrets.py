"""Populate local .env secrets without echoing them anywhere.

Run from the repo root:

    uv run --with argon2-cffi python scripts/init_secrets.py

Prompts (hidden input) for the admin password and, optionally, the Pinecone
and LangSmith API keys; writes them into .env in place and generates a random
SESSION_SECRET if one is not set. Nothing sensitive is printed. .env is
gitignored.
"""

from __future__ import annotations

import getpass
import pathlib
import re
import secrets

from argon2 import PasswordHasher

ENV = pathlib.Path(__file__).resolve().parents[1] / ".env"


def set_kv(text: str, key: str, value: str) -> str:
    line = f"{key}={value}"
    if re.search(rf"(?m)^{re.escape(key)}=", text):
        return re.sub(rf"(?m)^{re.escape(key)}=.*$", line, text)
    return text.rstrip() + "\n" + line + "\n"


def main() -> None:
    if not ENV.exists():
        raise SystemExit(".env not found — copy .env.example to .env first.")

    text = ENV.read_text()

    pw = getpass.getpass("Admin password (hidden, blank to skip): ")
    if pw:
        text = set_kv(text, "ADMIN_PASSWORD_HASH", PasswordHasher().hash(pw))

    if re.search(r"(?m)^SESSION_SECRET=\s*$", text):
        text = set_kv(text, "SESSION_SECRET", secrets.token_hex(32))

    pc = getpass.getpass("Pinecone API key (hidden, blank to skip): ")
    if pc:
        text = set_kv(text, "PINECONE_API_KEY", pc)

    ls = getpass.getpass("LangSmith API key (hidden, blank to skip): ")
    if ls:
        text = set_kv(text, "LANGSMITH_API_KEY", ls)

    ENV.write_text(text)
    print("Wrote secrets to .env (values not displayed).")


if __name__ == "__main__":
    main()
