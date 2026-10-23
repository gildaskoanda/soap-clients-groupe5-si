#!/usr/bin/env python3
"""
Configure Zabbix 7.0 pour superviser le service SOAP de clients (idempotent).

  1. importe le template « SOAP Clients Service » (zabbix/template_soap_clients.yaml)
  2. crée le groupe d'hôtes « SOAP Clients »
  3. crée l'hôte « soap-clients-app » (agent Zabbix + template SOAP + template Linux)

Usage (Zabbix démarré via docker compose, première connexion = Admin / zabbix) :
    python3 zabbix/setup_zabbix.py
Variables : ZABBIX_URL, ZABBIX_USER, ZABBIX_PASSWORD.
Bibliothèque standard uniquement.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

URL = os.environ.get("ZABBIX_URL", "http://localhost:8082/api_jsonrpc.php")
USER = os.environ.get("ZABBIX_USER", "Admin")
PASSWORD = os.environ.get("ZABBIX_PASSWORD", "zabbix")
HOST_NAME = "soap-clients-app"
GROUP_NAME = "SOAP Clients"
TEMPLATE_NAME = "SOAP Clients Service"
AGENT_DNS = "zabbix-agent"          # nom du service dans docker-compose.yml

_id = 0


def rpc(method, params, token=None):
    global _id
    _id += 1
    headers = {"Content-Type": "application/json-rpc"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps({"jsonrpc": "2.0", "method": method, "params": params, "id": _id}).encode()
    req = urllib.request.Request(URL, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        out = json.loads(r.read().decode())
    if "error" in out:
        e = out["error"]
        raise RuntimeError(f"{method} : {e.get('message')} - {e.get('data')}")
    return out["result"]


def wait_for_api(timeout=180):
    start = time.time()
    while time.time() - start < timeout:
        try:
            v = rpc("apiinfo.version", {})
            print(f"API Zabbix prête (version {v})")
            return
        except (urllib.error.URLError, ConnectionError, RuntimeError, json.JSONDecodeError):
            time.sleep(5)
    sys.exit("API Zabbix injoignable : vérifier `docker compose ps` (zabbix-web, zabbix-server).")


def main():
    wait_for_api()
    token = rpc("user.login", {"username": USER, "password": PASSWORD})
    print("Authentifié")

    # 1. Template
    source = (Path(__file__).with_name("template_soap_clients.yaml")).read_text(encoding="utf-8")
    on = {"createMissing": True, "updateExisting": True}
    rpc("configuration.import", {
        "format": "yaml", "source": source,
        "rules": {"template_groups": on, "templates": on, "items": {**on, "deleteMissing": True},
                  "triggers": {**on, "deleteMissing": True}, "graphs": {**on, "deleteMissing": True}},
    }, token)
    print("Template importé")

    # 2. Groupe d'hôtes
    groups = rpc("hostgroup.get", {"filter": {"name": [GROUP_NAME]}}, token)
    group_id = groups[0]["groupid"] if groups else rpc("hostgroup.create", {"name": GROUP_NAME}, token)["groupids"][0]

    # 3. Hôte
    tpl_ids = []
    for name in (TEMPLATE_NAME, "Linux by Zabbix agent"):
        res = rpc("template.get", {"filter": {"host": [name]}, "output": ["templateid"]}, token)
        if not res:
            sys.exit(f"Template introuvable : {name}")
        tpl_ids.append({"templateid": res[0]["templateid"]})

    if rpc("host.get", {"filter": {"host": [HOST_NAME]}}, token):
        print(f"Hôte {HOST_NAME} déjà présent : rien à faire")
        return
    rpc("host.create", {
        "host": HOST_NAME, "name": "Service SOAP clients (IBAM)",
        "groups": [{"groupid": group_id}], "templates": tpl_ids,
        "interfaces": [{"type": 1, "main": 1, "useip": 0, "ip": "", "dns": AGENT_DNS, "port": "10050"}],
    }, token)
    print(f"Hôte {HOST_NAME} créé. Interface web : {URL.replace('/api_jsonrpc.php', '')} (Monitoring > Latest data)")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        sys.exit(f"Échec : {exc}")
