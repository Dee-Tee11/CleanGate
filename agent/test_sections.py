"""Regression checks for RCM text extraction (see docs/registo_problemas.md).

Run: uv run python agent/test_sections.py
"""
import re
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import agent  # noqa: E402

SECTIONS = ("4.1", "4.2", "4.3", "4.4", "4.5", "4.6", "4.8", "4.9")

failures = []
for row in agent.manifest():
    text = agent.rcm_text(row["ficheiro"])
    for s in SECTIONS:
        sec = agent.section(text, s)
        if not sec or sec.split()[0].rstrip(".") != s or not 100 <= len(sec) <= 60000:
            failures.append(f"{row['substancia']} {s}: {len(sec or '')} chars")

# P-007: a cross-reference wrapped onto a new line ("secção\n6.1.") used to cut apixabano 4.3 short.
if len(agent.section(agent.rcm_text("apixabano.pdf"), "4.3")) < 1000:
    failures.append("apixabano 4.3 truncated (P-007)")

# P-008: table rows must stay together ("Depressão" on the same line as its frequency).
digoxina_48 = agent.section(agent.rcm_text("digoxina.pdf"), "4.8")
if not re.search(r"Pouco\s{2,}Depressão", digoxina_48):
    failures.append("digoxina 4.8 table rows split (P-008)")

# Name lookup inside ler_seccao_rcm: brand with dosage works, no guessing of near names.
for query, expected in [("Ben-U-Ron 500 mg", ["paracetamol"]), ("varfarina sódica", ["varfarina"]),
                        ("Lítio", ["lítio"]), ("Lantus", ["insulina glargina"]), ("rivaroxabano", []),
                        ("metilprednisolona", []), ("insulina", [])]:
    got = [r["substancia"] for r in agent.find_rcm(query)]
    if got != expected:
        failures.append(f"find_rcm({query!r}) = {got}, expected {expected}")

total = len(agent.manifest()) * len(SECTIONS)
print(f"{total} sections checked, {len(failures)} failures")
for f in failures:
    print("  FAIL", f)
sys.exit(1 if failures else 0)
