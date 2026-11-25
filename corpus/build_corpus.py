"""Build the ClinGate corpus: one RCM per substance from INFOMED (Infarmed) + manifest.csv.

Selection rule (a dataset design decision; keep it in sync with the validation plan):
  1. INFOMED filters: AIM authorised, marketed, non-generic.
  2. Single active substance matching the target (no fixed-dose combinations).
  3. Prefer oral solid forms (comprimido/capsula) when one exists.
  4. Lowest INFOMED MED ID (oldest registration, usually the reference medicine).
OVERRIDES replaces the rule for one substance, with the reason recorded in the manifest.

Usage: python3 corpus/build_corpus.py   (re-running re-downloads: a new corpus version)
"""
import csv
import datetime
import hashlib
import html
import http.cookiejar
import pathlib
import re
import subprocess
import time
import unicodedata
import urllib.parse
import urllib.request

BASE = "https://extranet.infarmed.pt/INFOMED-fo/"
ROOT = pathlib.Path(__file__).parent
SUBSTANCES = {
    "comum": ["paracetamol", "ibuprofeno", "metformina", "amoxicilina", "omeprazol", "atorvastatina",
              "ramipril", "bisoprolol", "sertralina", "salbutamol", "levotiroxina", "furosemida", "prednisolona"],
    "alto_risco": ["varfarina", "apixabano", "enoxaparina", "metotrexato", "lítio", "digoxina", "insulina glargina",
                   "amiodarona", "tramadol", "alprazolam", "claritromicina", "diclofenac"],
}
OVERRIDES = {}  # substance -> (med_id, reason)

OPENER = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def norm(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower().strip()


def fetch(path, data=None, ajax=False):
    headers = {"Faces-Request": "partial/ajax", "X-Requested-With": "XMLHttpRequest"} if ajax else {}
    body = urllib.parse.urlencode(data).encode() if data else None
    with OPENER.open(urllib.request.Request(BASE + path, body, headers), timeout=90) as r:
        return r.read()


def form_defaults(form):
    """Every field the browser would submit for this form, with its default value."""
    data = {}
    for tag in re.findall(r"<input[^>]*>", form):
        name, kind = re.search(r'name="([^"]*)"', tag), re.search(r'type="([^"]*)"', tag)
        if not name or "dt-medicamentos:" in name.group(1):
            continue
        if kind and kind.group(1) in ("checkbox", "radio") and "checked" not in tag:
            continue
        value = re.search(r'value="([^"]*)"', tag)
        data[name.group(1)] = html.unescape(value.group(1)) if value else ""
    for name, options in re.findall(r'<select[^>]*name="([^"]*)"[^>]*>(.*?)</select>', form, re.S):
        sel = re.search(r'<option[^>]*selected[^>]*value="([^"]*)"|<option[^>]*value="([^"]*)"[^>]*selected', options)
        data[name] = (sel.group(1) or sel.group(2)) if sel else ""
    return data


def parse_rows(xml):
    rows = []
    for tr in re.findall(r"<tr[^>]*data-ri[^>]*>.*?</tr>", xml, re.S):
        tr = re.sub(r"<script.*?</script>", "", tr, flags=re.S)
        c = [re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", td))).strip()
             for td in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        rows.append({"med_id": c[0], "nome": c[1].removeprefix("Autorizado").strip(), "dci": c[2],
                     "forma": c[3], "dosagem": c[4], "titular": c[5]})
    return rows


def search(substance):
    """All authorised, marketed, non-generic medicines whose DCI field matches `substance`."""
    page = fetch("pesquisa-avancada.xhtml").decode()
    data = form_defaults(re.search(r'<form id="mainForm".*?</form>', page, re.S).group(0))
    data.update({"mainForm:dci_input": substance, "mainForm:generico_input": "REF_INDICADOR:N",
                 "mainForm:estado-aim_input": "REF_EST_AIM:001",
                 "mainForm:estado-comercializacao_input": "REF_EST_COMERC:001",
                 "mainForm:dt-medicamentos_rppDD": "100"})

    def ajax(source, execute, extra):
        xml = fetch("pesquisa-avancada.xhtml", {
            **data, **extra, "javax.faces.partial.ajax": "true", "javax.faces.source": source,
            "javax.faces.partial.execute": execute, "javax.faces.partial.render": "mainForm:dt-medicamentos"},
            ajax=True).decode()
        if "<redirect" in xml:
            raise RuntimeError(f"INFOMED rejected the request for {substance!r}")
        data["javax.faces.ViewState"] = re.search(r"ViewState:0\"><!\[CDATA\[([^\]]*)", xml).group(1)
        return xml

    xml = ajax("mainForm:btnDoSearch", "mainForm:pnlCriterios mainForm:btnDoSearch",
               {"mainForm:btnDoSearch": "mainForm:btnDoSearch"})
    total = int(re.search(r"de um total de (\d+) registos", xml).group(1))
    rows = []
    for first in range(0, total, 100):  # the table only accepts its own page sizes (max 100)
        xml = ajax("mainForm:dt-medicamentos", "mainForm:dt-medicamentos", {
            "mainForm:dt-medicamentos": "mainForm:dt-medicamentos", "mainForm:dt-medicamentos_pagination": "true",
            "mainForm:dt-medicamentos_first": str(first), "mainForm:dt-medicamentos_rows": "100",
            "mainForm:dt-medicamentos_skipChildren": "true", "mainForm:dt-medicamentos_encodeFeature": "true"})
        rows += parse_rows(xml)
    return rows


def pick(substance, rows):
    target = re.compile(rf"\b{re.escape(norm(substance))}\b")
    single = [r for r in rows if "+" not in r["dci"] and target.search(norm(r["dci"]))]
    oral = [r for r in single if re.match(r"(comprimido|capsula)", norm(r["forma"]))]
    return min(oral or single, key=lambda r: int(r["med_id"]), default=None), len(single)


def has_key_sections(pdf):
    """Text is extractable (not a scan) and sections 4.2, 4.3 and 4.5 exist."""
    text = subprocess.run(["pdftotext", str(pdf), "-"], capture_output=True, text=True).stdout
    return all(re.search(rf"^\s*{s}\.?\s", text, re.M) for s in ("4.2", "4.3", "4.5"))


def rcm_last_update(med_id):
    """INFOMED's 'Última atualização' date for the RCM. Section 10 of the PDF is usually left blank."""
    page = html.unescape(fetch(f"detalhes-medicamento.xhtml?med_id={med_id}").decode())
    m = re.search(r"\(RCM\)\s*(?:<[^>]+>\s*)*Última atualização:\s*(?:<[^>]+>\s*)*(\d{2}/\d{2}/\d{4})", page)
    return m.group(1) if m else ""


def main():
    (ROOT / "rcm").mkdir(exist_ok=True)
    today = datetime.date.today().isoformat()
    manifest = []
    for group, substances in SUBSTANCES.items():
        for substance in substances:
            rows = search(substance)
            if substance in OVERRIDES:
                med_id, reason = OVERRIDES[substance]
                chosen, n = next(r for r in rows if r["med_id"] == med_id), len(rows)
            else:
                (chosen, n), reason = pick(substance, rows), "regra"
            if not chosen:
                print(f"!! {substance}: no single-substance non-generic medicine found")
                continue
            url = f"{BASE}download-ficheiro.xhtml?med_id={chosen['med_id']}&tipo_doc=rcm"
            pdf_bytes = fetch(url.removeprefix(BASE))
            if not pdf_bytes.startswith(b"%PDF"):
                print(f"!! {substance}: RCM for MED ID {chosen['med_id']} is not a PDF")
                continue
            path = ROOT / "rcm" / (norm(substance).replace(" ", "_") + ".pdf")
            path.write_bytes(pdf_bytes)
            sections_ok, revision = has_key_sections(path), rcm_last_update(chosen["med_id"])
            manifest.append({
                "ficheiro": path.name, "substancia": substance, "grupo": group, "nome_comercial": chosen["nome"],
                "titular": chosen["titular"], "forma": chosen["forma"], "dosagem": chosen["dosagem"],
                "med_id": chosen["med_id"], "data_revisao": revision, "fonte": "INFOMED", "url": url,
                "data_download": today, "selecao": reason, "candidatos": n, "seccoes_4_2_4_3_4_5": sections_ok,
                "sha256": hashlib.sha256(pdf_bytes).hexdigest()})
            print(f"{substance:18} {chosen['nome'][:28]:28} {chosen['dosagem'][:14]:14} "
                  f"{n:3} cand.  secções={'ok' if sections_ok else 'FALTAM'}  rev={revision or '?'}")
            time.sleep(1)  # be polite to a public service
    with open(ROOT / "manifest.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=manifest[0].keys())
        w.writeheader()
        w.writerows(manifest)
    print(f"\n{len(manifest)} RCMs -> {ROOT / 'manifest.csv'}")


if __name__ == "__main__":
    main()
