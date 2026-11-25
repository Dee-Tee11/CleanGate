# Registo de problemas

Problemas encontrados durante a construção do ClinGate, com a causa, a resolução e a evidência de que ficaram resolvidos. Os problemas não se apagam: um problema resolvido muda de estado e mantém o histórico.

**Estados:** `resolvido` · `resolvido com limitação` · `aberto`

## Resumo

| ID | Componente | Problema | Estado |
|---|---|---|---|
| P-001 | Agente (ferramentas) | O contexto do modelo enchia-se com o catálogo completo do corpus | resolvido com limitação |

---

## P-001 · O contexto do modelo enchia-se com o catálogo completo do corpus
- **Data:** 2026-11-25 · **Componente:** `agent/agent.py` (ferramentas do agente)
- **Problema:** o agente tinha uma ferramenta `listar_rcms` que devolvia os 25 medicamentos do corpus. O modelo chamava-a no início de todas as perguntas, mesmo quando só ia usar um RCM. Isto custava:
  - uma chamada extra ao modelo por pergunta, e cada chamada volta a enviar o contexto todo;
  - uma lista com 24 entradas desnecessárias (cerca de 320 tokens) a ocupar o contexto de todas as chamadas seguintes.
- **Causa:** o desenho das ferramentas separava "descobrir o documento" de "ler o documento". O modelo tinha de ver o catálogo antes de pedir o RCM.
- **Resolução:**
  - removida a `listar_rcms`;
  - a pesquisa passou para dentro da `ler_seccao_rcm` (função `find_rcm`): o modelo pede logo "varfarina, 4.5", e a ferramenta encontra o RCM pela substância ativa ou pelo nome comercial;
  - o contexto passou a conter só o RCM e a secção pedidos.

  A pesquisa procura o nome como palavra inteira e numa só direção:
  - "Ben-U-Ron 500 mg" encontra o paracetamol;
  - "insulina" não é interpretado como "insulina glargina";
  - "metilprednisolona" não corresponde a "prednisolona".
- **Efeito secundário detetado e corrigido:** sem a lista, o modelo não tinha a certeza de que um medicamento fora do corpus não existia e tentava outros nomes. Com o rivaroxabano fez 4 tentativas (incluindo "Xarelto" e "rivaroxaban") e gastou 11 915 tokens. A mensagem de "não existe" passou a dizer que a pesquisa já cobre a substância ativa e o nome comercial, e o modelo deixou de insistir.
- **Verificação** (smoke test de 2026-11-25, uma execução por pergunta, tokens medidos no LangSmith, projeto `CleanGate`):

  | Pergunta | Tokens de prompt antes | Depois | Chamadas ao modelo |
  |---|---|---|---|
  | Paracetamol | 8 354 | 5 134 (−39%) | 3 → 2 |
  | Metotrexato | 9 522 | 6 298 (−34%) | 3 → 2 |
  | Apixabano | 10 281 | 7 056 (−31%) | 3 → 2 |
  | Rivaroxabano (fora do corpus) | 4 tentativas na ferramenta | 1 tentativa | |

  - `uv run python agent/test_sections.py`: 7 casos de pesquisa por nome e 200 secções, 0 falhas.
  - Outputs: `runs/smoke_test_2026-11-25_pesquisa.txt` e `runs/smoke_test_2026-11-25_pesquisa_v2.txt`.
- **Limitação:** um nome mal escrito (por exemplo, "metrotexato") não é encontrado, e o agente responde que não tem informação. É uma falha segura: uma recusa em vez de uma resposta errada.
- **Estado:** resolvido com limitação

<!-- Modelo para cada entrada:

## P-00X · Título curto
- **Data:** AAAA-MM-DD · **Componente:**
- **Problema:**
- **Causa:**
- **Resolução:**
- **Verificação:**
- **Estado:**
-->
