# ClinGate

**Uma framework de validação para um assistente clínico baseado em LLM.**

O ClinGate responde a perguntas de médicos com base nos RCMs (Resumos das Características do Medicamento) do Infarmed. Mas o foco do projeto não é o agente: é a **validação à volta dele**. O objetivo é decidir, com evidência mensurável e reprodutível, se uma versão do sistema está pronta para produção, e conseguir defender essa decisão perante um auditor.

O contexto de referência é o de um dispositivo médico de software (MDR, Classe IIa): requisitos rastreáveis, test sets versionados, um release gate estatístico e documentação escrita para auditoria.

## Estado atual (semana 1 de 7)

- [x] Corpus de 25 RCMs com manifest versionado (fonte, data de revisão, SHA-256)
- [x] Agente mínimo (sistema sob teste), com citações por secção do RCM
- [x] Funções estatísticas do release gate (`stats.py`)
- [x] Testes de regressão da extração de texto e da pesquisa
- [x] Primeiros smoke tests, com traces no LangSmith
- [ ] Taxonomia de falhas e test set v1 (desenvolvimento + selado)
- [ ] Juiz LLM calibrado contra anotação humana
- [ ] Release gate global e por fatia
- [ ] Plano e relatório de validação

## Como funciona

```
pergunta do médico
      │
      ▼
agente (Deep Agents + gpt-oss-120b)
      │  ler_seccao_rcm("varfarina", "4.5")
      ▼
ferramenta: procura o RCM no corpus → extrai o texto do PDF → corta a secção 4.5
      │
      ▼
resposta com citação: [RCM Varfine 5 mg, secção 4.5]
```

O modelo nunca vê o PDF nem o corpus inteiro. Em cada chamada recebe apenas a secção que pediu.

## Decisões de desenho

| Decisão | Porquê |
|---|---|
| **Corpus fixo, com o SHA-256 de cada RCM** | Cada validação fica ligada à versão exata dos documentos. Se o Infarmed atualizar um RCM, o hash muda. |
| **Critério escrito para escolher o medicamento de cada substância** | Autorizado, comercializado, não genérico, uma só substância ativa, de preferência forma oral. A escolha é uma decisão de desenho do dataset e tem de ser reproduzível (`corpus/build_corpus.py`). |
| **Extração de texto (`pdftotext -layout`) e não OCR** | Os RCMs são PDFs digitais, com o texto já guardado no ficheiro. O OCR podia trocar números de doses. A extração é determinística e é testada. |
| **Pesquisa dentro da ferramenta, sem catálogo** | O modelo não recebe a lista dos 25 medicamentos, só o RCM que pede. Isto reduziu os tokens de prompt em 31–39% nas perguntas medidas (ver [P-001](docs/registo_problemas.md)). |
| **Modelo de pesos abertos (gpt-oss-120b, servido pela Groq)** | Os pesos fixos tornam o sistema sob teste reprodutível: o modelo não muda sem aviso. Isto também permite usar, mais tarde, um juiz de outra família, o que evita o enviesamento de auto-preferência. |
| **O release gate usa o limite inferior do intervalo de confiança, e não a média** | Com amostras pequenas, a média engana. Uma versão só passa se o limite inferior do IC de Wilson ficar acima do threshold (`stats.py`). |

## Primeiros resultados (smoke test)

Foram 6 perguntas (5 medicamentos do corpus, 4 deles de alto risco, e 1 fora do corpus), corridas em vários dias, com cada resposta verificada contra o RCM.

- **As respostas não são determinísticas.** A mesma pergunta sobre o lítio falhou numa execução (intervalo terapêutico errado, mas com citação) e passou noutra. Uma execução não é evidência: é preciso medir com pass^k.
- **Há uma falha consistente.** Na interação varfarina + ibuprofeno, o agente sugeriu paracetamol como alternativa, sem citação. O próprio RCM da varfarina lista o paracetamol (em uso prolongado) entre os medicamentos que potenciam o seu efeito.
- **As instruções não garantem o comportamento.** Mesmo com "nunca uses conhecimento próprio" no prompt, o modelo acrescentou critérios que não estão no RCM. É por isso que a avaliação precisa de avaliadores, e não apenas de prompts.
- **Fora do corpus, o agente recusa corretamente.** Perguntado sobre o rivaroxabano, diz que não tem informação em vez de inventar.

## Como correr

Requisitos: Python 3.13, [uv](https://docs.astral.sh/uv/) e `pdftotext` (poppler-utils).

```bash
uv sync

# .env (não versionar)
#   GROQ_API_KEY=...
#   LANGSMITH_TRACING=true     # opcional: traces no LangSmith
#   LANGSMITH_PROJECT=CleanGate
#   LANGSMITH_API_KEY=...

uv run python corpus/build_corpus.py          # (re)constrói o corpus a partir do INFOMED
uv run --env-file .env agent/agent.py "Qual a posologia do metotrexato na artrite reumatoide?"

uv run python agent/test_sections.py          # testes de regressão da extração e da pesquisa
uv run python stats.py                        # verificações das funções estatísticas
```

Reconstruir o corpus gera uma nova versão: os hashes no manifest identificam-na.

## Estrutura

```
agent/
  agent.py              sistema sob teste (Deep Agents)
  test_sections.py      testes de regressão: extração das secções e pesquisa por nome
corpus/
  build_corpus.py       descarrega os RCMs do INFOMED e gera o manifest
  manifest.csv          medicamento, titular, data de revisão, URL, SHA-256
  rcm/                  25 RCMs em PDF
docs/
  registo_problemas.md  problemas observados, com causa, resolução e evidência
  possiveis_problemas.md  riscos por verificar
runs/                   outputs das execuções
stats.py                IC de Wilson, regra dos três, tamanho de amostra, McNemar
```

## Roadmap

| Semana | Foco |
|---|---|
| 1 | Estatística de avaliação, corpus, agente mínimo |
| 2 | Análise de erros, taxonomia de falhas, test set v1 (desenvolvimento + selado) |
| 3 | Juiz LLM, anotação, Cohen's kappa, pass^k |
| 4 | Avaliação de trajetórias, prompt injection indireta nos RCMs, release gate |
| 5 | Plano de validação, requisitos, matriz de rastreabilidade |
| 6 | Monitorização: drift, regressões, amostragem por risco |
| 7 | Validação v1.0 vs v1.1 e relatório de validação |

---

*Este é um projeto de portfólio e não é um dispositivo médico. As respostas do agente não devem ser usadas em decisões clínicas.*
