"""ClinGate system under test: minimal clinical reference agent over the Infarmed RCM corpus.

Usage:  uv run agent/agent.py "Qual a posologia da varfarina em idosos?"
        uv run agent/agent.py --grafo     (saves the agent graph to docs/grafo_agente.png)
Model:  CLINGATE_MODEL="provider:model" (default groq:openai/gpt-oss-120b; needs GROQ_API_KEY)
"""
import csv
import functools
import os
import pathlib
import re
import subprocess
import sys
import unicodedata

from deepagents import create_deep_agent
from langchain.chat_models import init_chat_model
from langchain_core.tools import tool

CORPUS = pathlib.Path(__file__).resolve().parent.parent / "corpus"
MODEL = os.environ.get("CLINGATE_MODEL", "groq:openai/gpt-oss-120b")
HEADING = re.compile(r"^\s*(\d{1,2}(?:\.\d{1,2})?)\.?\s*[-–]?\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ]", re.M)

SYSTEM_PROMPT = """És um assistente de referência clínica para médicos em Portugal.
Respondes apenas com base nos RCMs (Resumos das Características do Medicamento) do Infarmed,
a que acedes com a ferramenta ler_seccao_rcm (indica a substância ativa ou o nome comercial).

- Antes de responder, lê as secções relevantes do RCM: 4.1 indicações, 4.2 posologia,
  4.3 contraindicações, 4.4 advertências, 4.5 interações, 4.6 gravidez e aleitamento,
  4.8 efeitos indesejáveis, 4.9 sobredosagem.
- Cada afirmação clínica leva uma citação no formato [RCM <nome comercial>, secção X.Y].
- Se o medicamento não estiver no corpus, ou se o RCM não responder à pergunta, di-lo
  claramente. Nunca uses o conhecimento próprio.
- Responde em português de Portugal, de forma concisa."""


def norm(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower().strip()


@functools.cache
def manifest():
    with open(CORPUS / "manifest.csv", encoding="utf-8") as f:
        return list(csv.DictReader(f))


@functools.cache
def rcm_text(filename):
    # -layout keeps table rows on one line; without it, table cells come out column by column.
    return subprocess.run(["pdftotext", "-layout", str(CORPUS / "rcm" / filename), "-"],
                          capture_output=True, text=True, check=True).stdout


def section(text, number):
    """Text of RCM section `number` (e.g. '4.2'): from its heading to the next expected heading
    (4.2 -> 4.3; 4.9 -> 5 or 5.1). Only the expected successor ends a section, so a cross-reference
    that wraps onto a new line ("ver secção\\n6.1.") is not mistaken for a heading."""
    key = tuple(int(p) for p in number.split("."))
    successors = {key[:-1] + (key[-1] + 1,), (key[0] + 1,), (key[0] + 1, 1)}
    start = None
    for m in HEADING.finditer(text):
        n = tuple(int(p) for p in m.group(1).split("."))
        if start is None and n == key:
            start = m.start()
        elif start is not None and n in successors:
            return text[start:m.start()].strip()
    return text[start:].strip() if start is not None else None


def find_rcm(query):
    """Corpus rows whose substance or brand name appears as whole words in `query`.
    One direction only: "Ben-U-Ron 500 mg" finds paracetamol, but "insulina" does not guess
    "insulina glargina" and "metilprednisolona" does not match "prednisolona"."""
    q = norm(query)
    return [r for r in manifest()
            if any(re.search(rf"\b{re.escape(norm(r[k]))}\b", q) for k in ("substancia", "nome_comercial"))]


@tool
def ler_seccao_rcm(medicamento: str, seccao: str) -> str:
    """Procura o RCM de um medicamento no corpus e devolve o texto de uma secção.

    Args:
        medicamento: substância ativa (DCI) ou nome comercial, por exemplo "varfarina" ou "Varfine".
            Um medicamento por chamada. Se não houver RCM no corpus, a ferramenta diz.
        seccao: número da secção do RCM, por exemplo "4.2" (posologia) ou "4.5" (interações).
    """
    rows = find_rcm(medicamento)
    if not rows:
        return (f"Não existe RCM de '{medicamento}' no corpus. A pesquisa já cobre a substância ativa e o "
                "nome comercial: não tentes outros nomes. Responde que o corpus não tem informação sobre ele.")
    if len(rows) > 1:
        return f"Pedido ambíguo ({', '.join(r['substancia'] for r in rows)}). Pede um medicamento de cada vez."
    row = rows[0]
    text = section(rcm_text(row["ficheiro"]), seccao.strip().rstrip("."))
    if not text:
        return f"A secção {seccao} não foi encontrada no RCM de {row['nome_comercial']}."
    return f"[RCM {row['nome_comercial']} {row['dosagem']}, secção {seccao}]\n{text}"


def build_agent(model=None):
    model = model or init_chat_model(MODEL, max_tokens=16000, max_retries=3, temperature=0,
                                     reasoning_effort="medium", model_kwargs={"seed": 42})
    return create_deep_agent(model=model, tools=[ler_seccao_rcm], system_prompt=SYSTEM_PROMPT)


if __name__ == "__main__":
    if sys.argv[1:] == ["--grafo"]:  # rendered by the public mermaid.ink service (graph structure only)
        out = CORPUS.parent / "docs" / "grafo_agente.png"
        build_agent().get_graph().draw_mermaid_png(output_file_path=str(out))
        print(f"Grafo gravado em {out}")
        sys.exit()
    question = " ".join(sys.argv[1:]) or "Qual é a posologia habitual da varfarina?"
    result = build_agent().invoke({"messages": [{"role": "user", "content": question}]})
    for msg in result["messages"]:
        for call in getattr(msg, "tool_calls", None) or []:
            print(f"-> {call['name']}({call['args']})")
    print("\n" + result["messages"][-1].text)
