#!/usr/bin/env python3
"""
Tests fonctionnels SOAP du service clients (WSDL, 3 opérations, Faults).

Usage :
  python3 tests/e2e/run_soap_tests.py                       # contre http://localhost:8080 (Docker Compose)
  python3 tests/e2e/run_soap_tests.py --url http://127.0.0.1:8099 --db-down harness   # serveur de test sans Docker
  python3 tests/e2e/run_soap_tests.py --db-down docker      # coupe/relance le conteneur mongo (docker compose)
  python3 tests/e2e/run_soap_tests.py --db-down skip        # ignore le test d'indisponibilité

Sortie : tableau PASS/FAIL, code retour 0 si tout passe, et un rapport Markdown (--report).
Aucune dépendance externe (bibliothèque standard uniquement).
"""
import argparse
import subprocess
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

NS = "urn:ibam:clients:v1"
ENV = "http://schemas.xmlsoap.org/soap/envelope/"


def q(tag):
    return f"{{{NS}}}{tag}"


class Soap:
    def __init__(self, base):
        self.base = base.rstrip("/")
        self.endpoint = self.base + "/soap/clients"

    def get_wsdl(self):
        with urllib.request.urlopen(self.endpoint + "?wsdl", timeout=10) as r:
            return r.status, r.read().decode()

    def call(self, op, fields, raw=None):
        """Envoie une requête ; retourne (statut_http, racine_xml_du_Body|None, fault_dict|None)."""
        if raw is None:
            inner = "".join(f"<c:{k}>{v}</c:{k}>" for k, v in fields)
            raw = (f'<?xml version="1.0" encoding="UTF-8"?><soapenv:Envelope xmlns:soapenv="{ENV}" '
                   f'xmlns:c="{NS}"><soapenv:Body><c:{op}Request>{inner}</c:{op}Request></soapenv:Body></soapenv:Envelope>')
        req = urllib.request.Request(self.endpoint, data=raw.encode(), method="POST", headers={
            "Content-Type": "text/xml; charset=utf-8", "SOAPAction": f"{NS}#{op}"})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                status, body = r.status, r.read().decode()
        except urllib.error.HTTPError as e:
            status, body = e.code, e.read().decode()
        root = ET.fromstring(body)
        b = root.find(f"{{{ENV}}}Body")
        fault = b.find(f"{{{ENV}}}Fault")
        if fault is not None:
            d = fault.find("detail/" + q("ClientFault"))
            return status, None, {
                "faultcode": (fault.findtext("faultcode") or "").split(":")[-1],
                "faultstring": fault.findtext("faultstring"),
                "code": d.findtext(q("code")) if d is not None else None,
                "champ": d.findtext(q("champ")) if d is not None else None,
            }
        return status, b[0], None


def client_dict(el):
    return {c.tag.split("}")[1]: c.text for c in el}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8080")
    ap.add_argument("--db-down", choices=["skip", "harness", "docker"], default="skip")
    ap.add_argument("--report", help="écrit un rapport Markdown")
    a = ap.parse_args()

    s = Soap(a.url)
    results = []

    def check(name, expected, fn):
        try:
            obtained = fn()
            ok = obtained is True or obtained == expected
            results.append((name, expected, "OK" if obtained is True else str(obtained), ok))
        except Exception as e:  # noqa: BLE001
            results.append((name, expected, f"EXCEPTION {type(e).__name__}: {e}", False))

    if a.db_down == "harness":
        urllib.request.urlopen(a.url.rstrip("/") + "/_test/reset", timeout=5).read()

    CODE = "CLI-000010"

    # --- WSDL -----------------------------------------------------------------
    def t_wsdl():
        st, body = s.get_wsdl()
        ops = all(f'operation name="{o}"' in body for o in ("getClientDetails", "searchClients", "updateClient"))
        return True if st == 200 and ops and "__ENDPOINT__" not in body else f"{st} ops={ops}"
    check("T01 WSDL publié avec les 3 opérations", "HTTP 200 + 3 opérations", t_wsdl)

    # --- getClientDetails -----------------------------------------------------
    def t_get_ok():
        st, el, f = s.call("getClientDetails", [("codeClient", CODE)])
        c = client_dict(el.find(q("client")))
        return True if st == 200 and c["codeClient"] == CODE and c["version"].isdigit() else (st, f, c)
    check("T02 getClientDetails : client existant", "HTTP 200, client CLI-000010", t_get_ok)

    def t_get_404():
        st, _, f = s.call("getClientDetails", [("codeClient", "CLI-999999")])
        return (st, f["faultcode"], f["code"])
    check("T03 getClientDetails : client inexistant", (500, "Client", "CLIENT_NOT_FOUND"), t_get_404)

    def t_get_invalid():
        st, _, f = s.call("getClientDetails", [("codeClient", "ABC")])
        return (st, f["code"], f["champ"])
    check("T04 getClientDetails : code invalide", (500, "VALIDATION_ERROR", "codeClient"), t_get_invalid)

    # --- searchClients --------------------------------------------------------
    def t_search_nom():
        st, el, f = s.call("searchClients", [("nom", "kone")])
        items = [client_dict(c) for c in el.findall(q("clients"))]
        return True if st == 200 and int(el.findtext(q("total"))) >= 1 and items and all(i["nom"] == "KONE" for i in items) else (st, f)
    check("T05 searchClients : par nom (insensible à la casse)", "tous les résultats ont nom=KONE", t_search_nom)

    def t_search_page():
        st, el, f = s.call("searchClients", [("statut", "actif"), ("page", "2"), ("taillePage", "3")])
        items = el.findall(q("clients"))
        return (st, el.findtext(q("page")), el.findtext(q("taillePage")), len(items), int(el.findtext(q("total"))) > 3)
    check("T06 searchClients : filtre statut + pagination", (200, "2", "3", 3, True), t_search_page)

    def t_search_size():
        st, _, f = s.call("searchClients", [("taillePage", "1000")])
        return (st, f["code"], f["champ"])
    check("T07 searchClients : taillePage hors limites", (500, "VALIDATION_ERROR", "taillePage"), t_search_size)

    def t_search_statut():
        st, _, f = s.call("searchClients", [("statut", "banni")])
        return (st, f["code"], f["champ"])
    check("T08 searchClients : statut hors énumération", (500, "VALIDATION_ERROR", "statut"), t_search_statut)

    def t_search_empty():
        st, el, f = s.call("searchClients", [("nom", "ZZZINEXISTANT")])
        return (st, el.findtext(q("total")), len(el.findall(q("clients"))))
    check("T09 searchClients : aucun résultat (pas une erreur)", (200, "0", 0), t_search_empty)

    # --- updateClient ---------------------------------------------------------
    stamp = str(int(time.time()))[-6:]
    ville = f"Test{stamp}"

    def current_version():
        _, el, _ = s.call("getClientDetails", [("codeClient", CODE)])
        return int(client_dict(el.find(q("client")))["version"])

    state = {}

    def t_upd_ok():
        v = current_version()
        state["v"] = v
        st, el, f = s.call("updateClient", [("codeClient", CODE), ("versionAttendue", v), ("ville", ville), ("statut", "suspendu")])
        c = client_dict(el.find(q("client")))
        return True if (st == 200 and c["ville"] == ville and c["statut"] == "suspendu" and int(c["version"]) == v + 1
                        and c["synchronisation"] == "pending_mysql") else (st, f, c)
    check("T10 updateClient : modification valide (version+1, pending_mysql)", "HTTP 200, version incrémentée", t_upd_ok)

    def t_upd_persist():
        _, el, _ = s.call("getClientDetails", [("codeClient", CODE)])
        c = client_dict(el.find(q("client")))
        return (c["ville"], c["statut"])
    check("T11 cohérence : relecture après mise à jour", (ville, "suspendu"), t_upd_persist)

    def t_upd_conflict():
        st, _, f = s.call("updateClient", [("codeClient", CODE), ("versionAttendue", state["v"]), ("ville", "Autre")])
        return (st, f["code"], f["champ"])
    check("T12 updateClient : conflit de version (verrou optimiste)", (500, "VERSION_CONFLICT", "versionAttendue"), t_upd_conflict)

    def t_upd_email():
        st, _, f = s.call("updateClient", [("codeClient", CODE), ("email", "pas-un-email")])
        return (st, f["code"], f["champ"])
    check("T13 updateClient : e-mail invalide", (500, "VALIDATION_ERROR", "email"), t_upd_email)

    def t_upd_dup():
        _, el, _ = s.call("getClientDetails", [("codeClient", "CLI-000011")])
        other = client_dict(el.find(q("client")))["email"]
        st, _, f = s.call("updateClient", [("codeClient", CODE), ("email", other)])
        return (st, f["code"], f["champ"])
    check("T14 updateClient : e-mail déjà utilisé", (500, "EMAIL_ALREADY_USED", "email"), t_upd_dup)

    def t_upd_empty():
        st, _, f = s.call("updateClient", [("codeClient", CODE)])
        return (st, f["code"])
    check("T15 updateClient : aucun champ à modifier", (500, "VALIDATION_ERROR"), t_upd_empty)

    def t_upd_404():
        st, _, f = s.call("updateClient", [("codeClient", "CLI-999999"), ("ville", "Nowhere")])
        return (st, f["code"])
    check("T16 updateClient : client inexistant", (500, "CLIENT_NOT_FOUND"), t_upd_404)

    def t_upd_phone():
        st, _, f = s.call("updateClient", [("codeClient", CODE), ("telephone", "12")])
        return (st, f["code"], f["champ"])
    check("T17 updateClient : téléphone invalide", (500, "VALIDATION_ERROR", "telephone"), t_upd_phone)

    # --- enveloppe invalide ----------------------------------------------------
    def t_malformed():
        st, _, f = s.call("x", [], raw="<not-soap/>")
        return st in (400, 500) and f is not None
    check("T18 enveloppe SOAP invalide -> Fault", "Fault HTTP 400/500", t_malformed)

    # --- indisponibilité de la base -----------------------------------------
    if a.db_down != "skip":
        def down():
            if a.db_down == "harness":
                urllib.request.urlopen(a.url.rstrip("/") + "/_test/down", timeout=5).read()
            else:
                subprocess.run(["docker", "compose", "stop", "mongo"], check=True, capture_output=True)
                time.sleep(2)

        def up():
            if a.db_down == "harness":
                urllib.request.urlopen(a.url.rstrip("/") + "/_test/up", timeout=5).read()
            else:
                subprocess.run(["docker", "compose", "start", "mongo"], check=True, capture_output=True)
                time.sleep(8)

        def t_db_down():
            down()
            try:
                st, _, f = s.call("getClientDetails", [("codeClient", CODE)])
                return (st, f["faultcode"], f["code"])
            finally:
                up()
        check("T19 MongoDB indisponible -> Fault serveur", (500, "Server", "SERVICE_UNAVAILABLE"), t_db_down)

        def t_db_back():
            st, el, f = s.call("getClientDetails", [("codeClient", CODE)])
            return True if st == 200 else (st, f)
        check("T20 reprise après retour de MongoDB", "HTTP 200", t_db_back)

    # --- rapport ---------------------------------------------------------------
    width = max(len(r[0]) for r in results)
    passed = sum(1 for r in results if r[3])
    print()
    for name, exp, got, ok in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name.ljust(width)}" + ("" if ok else f"\n      attendu : {exp}\n      obtenu  : {got}"))
    print(f"\n{passed}/{len(results)} tests réussis")

    if a.report:
        with open(a.report, "w", encoding="utf-8") as fh:
            fh.write(f"# Résultats des tests SOAP\n\nCible : `{a.url}` — mode indisponibilité base : `{a.db_down}`\n\n")
            fh.write("| # | Test | Résultat attendu | Statut |\n|---|---|---|---|\n")
            for i, (name, exp, got, ok) in enumerate(results, 1):
                fh.write(f"| {i} | {name} | {str(exp).replace('|', '/')} | {'✅ PASS' if ok else '❌ FAIL — ' + str(got).replace('|', '/')} |\n")
            fh.write(f"\n**Bilan : {passed}/{len(results)} tests réussis.**\n")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
