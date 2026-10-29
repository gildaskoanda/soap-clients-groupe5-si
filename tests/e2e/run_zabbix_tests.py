#!/usr/bin/env python3
"""Vérifie Zabbix ; --simulate-outage autorise une coupure locale de MongoDB.

Bibliothèque standard uniquement. Le redémarrage est tenté dans un bloc finally.
Ne pas exécuter sur un environnement partagé ou de production.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "zabbix"))
import setup_zabbix as z  # noqa: E402
from run_soap_tests import Soap  # noqa: E402


def wait_until(label, predicate, timeout=150):
    print(f"Attente : {label}", flush=True)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = predicate()
        if result:
            return result
        time.sleep(3)
    raise TimeoutError(label)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--simulate-outage", action="store_true")
    parser.add_argument("--report", type=Path, default=ROOT / "docs/RESULTATS_ZABBIX.md")
    args = parser.parse_args()
    if args.simulate_outage and urlparse(z.URL).hostname not in {"localhost", "127.0.0.1"}:
        parser.error("La simulation de panne est limitée au Zabbix local.")

    results, evidence = [], {}
    token = None
    started = int(time.time())

    def check(label, condition):
        results.append((label, bool(condition)))
        print(f"{'PASS' if condition else 'FAIL'} {label}", flush=True)
        if not condition:
            raise AssertionError(label)

    def rpc(method, params):
        return z.rpc(method, params, token)

    def compose(*arguments):
        subprocess.run(["docker", "compose", *arguments], cwd=ROOT, check=True, timeout=90)

    try:
        version = rpc("apiinfo.version", [])
        evidence["version_zabbix"] = version
        check("Z01 API Zabbix 7.0 accessible", version.startswith("7.0."))
        token = z.rpc("user.login", {"username": z.USER, "password": z.PASSWORD})
        hosts = rpc("host.get", {"filter": {"host": [z.HOST_NAME]}, "output": ["hostid"]})
        if len(hosts) != 1:
            raise RuntimeError("Exécuter d’abord zabbix/setup_zabbix.py")
        host_id = hosts[0]["hostid"]

        def items():
            data = rpc("item.get", {"hostids": [host_id], "search": {"key_": "soap."},
                "output": ["key_", "value_type", "state", "lastclock", "lastvalue", "error"]})
            return {item["key_"]: item for item in data}

        def collected():
            data = items()
            return data if len(data) == 14 and all(
                item["state"] == "0" and int(item["lastclock"]) > time.time() - 180
                for item in data.values()) else None

        data = wait_until("collecte des 14 indicateurs", collected)
        evidence["collecte_initiale"] = data
        check("Z02 les 14 indicateurs sont supportés et récents", len(data) == 14)
        check("Z03 décimales et sentinelle négative représentables",
              data["soap.latency.avg"]["value_type"] == "0" and data["soap.etl.age"]["value_type"] == "0")
        check("Z04 consultation SOAP, WSDL et données corrects", all(
            data[key]["lastvalue"] == value for key, value in {
                "soap.check.ok": "1", "soap.wsdl.operations": "3", "soap.clients.total": "201",
                "soap.mongodb.up": "1", "soap.etl.rejected": "7"}.items()))

        if args.simulate_outage:
            def trigger():
                values = rpc("trigger.get", {"hostids": [host_id], "filter": {
                    "description": "MongoDB indisponible pour le service SOAP"},
                    "output": ["triggerid", "description", "value", "lastchange"]})
                if len(values) != 1:
                    raise RuntimeError("Déclencheur MongoDB introuvable")
                return values[0]

            def trigger_state(value):
                current = trigger()
                return current if current["value"] == value else None

            soap = Soap("http://127.0.0.1:8080")
            try:
                compose("stop", "mongo")
                status, _, fault = soap.call("getClientDetails", [("codeClient", "CLI-000010")])
                check("Z05 panne réelle : Fault SERVICE_UNAVAILABLE", status == 500 and
                      fault is not None and fault["code"] == "SERVICE_UNAVAILABLE")
                problem = wait_until("alerte MongoDB active", lambda: trigger_state("1"))
                evidence["alerte"] = problem
                check("Z06 Zabbix détecte la panne réelle", problem["value"] == "1")
            finally:
                compose("start", "mongo")

            def soap_ready():
                try:
                    return soap.call("getClientDetails", [("codeClient", "CLI-000010")])[0] == 200
                except (OSError, ValueError):
                    return False

            check("Z07 consultation SOAP rétablie", wait_until("retour du service SOAP", soap_ready))
            recovery = wait_until("résolution de l’alerte MongoDB", lambda: trigger_state("0"))
            evidence["retablissement"] = recovery
            check("Z08 Zabbix constate le retour à la normale", recovery["value"] == "0")
            events = rpc("event.get", {"objectids": [recovery["triggerid"]], "time_from": started,
                "output": ["eventid", "clock", "value", "name"], "sortfield": ["clock", "eventid"], "sortorder": "ASC"})
            evidence["evenements"] = events
            check("Z09 événements de panne et de reprise enregistrés", {e["value"] for e in events} == {"0", "1"})
            evidence["collecte_finale"] = wait_until("reprise de tous les indicateurs", collected)
    except Exception as exc:
        if not results or results[-1][1]:
            results.append((f"Exécution interrompue : {type(exc).__name__}: {exc}", False))
        print(f"Échec : {exc}", flush=True)
    finally:
        if token:
            try:
                rpc("user.logout", [])
            except Exception:
                pass
        passed = sum(ok for _, ok in results)
        report = ["# Résultats des tests Zabbix", "",
            f"Exécution UTC : {datetime.now(timezone.utc).isoformat()}", "",
            f"Panne réelle autorisée : {args.simulate_outage}", "",
            "| Contrôle | Résultat |", "|---|---|"]
        report += [f"| {label.replace('|', '/')} | {'PASS' if ok else 'FAIL'} |" for label, ok in results]
        report += ["", f"**Bilan : {passed}/{len(results)} contrôles réussis.**", "",
            "Les identifiants ci-dessous désignent les événements locaux, sans secret de connexion.", "",
            "```json", json.dumps(evidence, ensure_ascii=False, indent=2), "```", ""]
        args.report.write_text("\n".join(report), encoding="utf-8")
    return 0 if results and all(ok for _, ok in results) else 1


if __name__ == "__main__":
    sys.exit(main())
