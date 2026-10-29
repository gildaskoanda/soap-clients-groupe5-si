#!/usr/bin/env python3
"""Crée une configuration locale avec des secrets aléatoires, sans écraser .env."""
import base64
import os
from pathlib import Path
import secrets


def main():
    root = Path(__file__).resolve().parents[1]
    target = root / ".env"
    if target.exists():
        print(".env existe déjà : configuration conservée.")
        return
    replacements = {
        "MYSQL_ROOT_PASSWORD": secrets.token_hex(24),
        "MYSQL_PASSWORD": secrets.token_hex(24),
        "MONGO_ROOT_PASSWORD": secrets.token_hex(24),
        "MONGO_APP_PASSWORD": secrets.token_hex(24),
        "AIRFLOW_ADMIN_PASSWORD": secrets.token_hex(16),
        "AIRFLOW_SECRET_KEY": secrets.token_hex(32),
        "ZABBIX_DB_PASSWORD": secrets.token_hex(24),
        "APP_KEY": "base64:" + base64.b64encode(secrets.token_bytes(32)).decode(),
    }
    lines = []
    for line in (root / ".env.example").read_text(encoding="utf-8").splitlines():
        key = line.split("=", 1)[0]
        lines.append(f"{key}={replacements[key]}" if key in replacements else line)
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write("\n".join(lines) + "\n")
    print("Configuration créée dans .env. Conservez ce fichier localement.")


if __name__ == "__main__":
    main()
