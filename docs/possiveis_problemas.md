# Possíveis problemas

Riscos identificados que ainda **não foram observados**. Cada um tem uma forma de verificação. Quando um risco se confirma, passa para o [registo de problemas](registo_problemas.md) com a evidência. Quando se descarta, fica aqui marcado como descartado, com a razão.

**Estados:** `por verificar` · `confirmado → P-xxx` · `descartado`

## Resumo

| ID | Componente | Possível problema | Estado |
|---|---|---|---|
| R-001 | Modelo (gpt-oss-120b) | Qualidade do português nas respostas | por verificar |

---

## R-001 · Qualidade do português nas respostas
- **Data:** 2026-11-24 · **Componente:** modelo do sistema sob teste (gpt-oss-120b)
- **Possível problema:** o modelo pode responder num português inadequado para médicos em Portugal:
  - em português do Brasil em vez de português europeu ("você", "arquivo", gerúndio como "estou fazendo");
  - com termos em inglês misturados na resposta;
  - com termos clínicos mal traduzidos (o mais grave).
- **Porque é plausível:** o gpt-oss foi treinado sobretudo em inglês.
- **O que joga a favor:** as respostas baseiam-se no texto dos RCMs, que já está em português europeu. Quando o modelo cita a fonte, tende a copiar a terminologia correta.
- **Gravidade:** a correção clínica pesa mais do que a qualidade do português. Uma resposta num português desajeitado mas com a dose certa é menos perigosa do que uma resposta fluente com a dose errada. Uma falha clínica bloqueia o release; uma falha de linguagem pode ter um limite mais tolerante.
- **Como verificar:** no smoke test, avaliar cada resposta quanto ao idioma: português europeu, português do Brasil ou mistura com inglês.
- **Se se confirmar:**
  1. Criar um requisito com critério de aceitação (por exemplo, 100% das respostas em português europeu).
  2. Verificá-lo com um avaliador automático e determinístico que procura marcas do português do Brasil.
  3. Se o modelo não cumprir, comparar modelos nas mesmas perguntas (gpt-oss-120b vs Qwen ou outro), mudando apenas `CLINGATE_MODEL`, desde que o modelo alternativo suporte chamadas a ferramentas.
- **Estado:** por verificar
