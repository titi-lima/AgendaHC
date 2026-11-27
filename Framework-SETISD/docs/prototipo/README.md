# AgendaHC · protótipo v0.1.0

Protótipo da fila priorizada de solicitações de exame da Central de Marcação do HC-UFPE, construído sobre o Framework SETISD (FastAPI + Vue 3). Uso interno: não há tela para o paciente e o AGHU continua sendo o sistema oficial (o AgendaHC só lê).

## Telas

| Tela | O que mostra |
| :--- | :--- |
| [Fila de marcação](screenshots/01-fila.png) | Pacientes ordenados pela regra da unidade, todos os exames pendentes de cada um, espera, motivo da posição e alerta de combinação. |
| [Detalhe do paciente](screenshots/02-detalhe-combinacao.png) | Exames, combinação de exames com orientação, lista de prioridade, dados ausentes no extrato e histórico. |
| [Incluir na lista](screenshots/03a-incluir-prioridade.png) · [reordenação](screenshots/03-reordenacao-prioridade.png) | A inclusão exige área, motivo e "Vale para" visível. Ao confirmar, a fila se reordena na frente do marcador, a linha mostra quantas posições subiu e o aviso oferece "Desfazer". |
| [Registrar resultado](screenshots/04-registrar-resultado.png) · [depois](screenshots/05-apos-registro.png) | O marcador registra "Agendado no AGHU" com a data (ou "Cancelado" com o motivo); o paciente sai da fila, o aviso oferece "Desfazer" e tudo fica no histórico e na auditoria. |
| [Painel da gestão](screenshots/06-painel.png) | Pendentes, espera acima de 60 dias e distribuição da espera por unidade. |
| [Tela menor (1366×768)](screenshots/09-compacto-1366.png) | Com o detalhe aberto, data e status passam para a linha de baixo; o status mostra a hora do contato. |
| [Regras de prioridade](screenshots/07-regras.png) · [listas](screenshots/08-regras-listas.png) | Ordem dos critérios por unidade (versionada), lista de prioridade e combinações de exames. Ao voltar para a fila depois de mudar uma regra, as linhas deslizam para a nova posição. |

## O que é real e o que é exemplo

- **Dados do repositório:** `data/solicitacoes_sinteticas.csv` tem a mesma estrutura e distribuição do extrato anonimizado do AGHU enviado pela TI do HC (576 itens, 415 pacientes, 49 exames, ago–set/2026), mas prontuários, nomes, códigos de solicitação e profissionais são fictícios. As datas foram deslocadas para que a solicitação mais recente seja de 25/11/2026, então a espera (contada até hoje) fica parecida com a do extrato recém-tirado. As capturas de tela usam esses dados.
- **Extrato real:** fica fora do Git (`data/solicitacoes.csv` está no `.gitignore`). Para usá-lo localmente, baixe o CSV do Drive da turma e aponte `SOLICITACAO_CSV_PATH` para ele no `.env`.
- **Exemplo (marcado como tal na interface):** a ordem dos critérios, os 6 pacientes da lista de prioridade (nefrologia/oncologia) e as 6 combinações de exames, montadas a partir dos pares mais frequentes no extrato. Tudo precisa ser validado com a Central e a UDI.
- **Ausente:** data de retorno, município e telefone não estão no extrato. A interface diz isso em vez de inventar; entram como critérios quando a TI incluir os campos.

## Como rodar

```bash
cp .env.example .env
```

```bash
./dev.sh
```

Por padrão o sistema lê `data/solicitacoes_sinteticas.csv`. Acesse http://localhost:5173 com o login mock `admin` / `admin`. Na primeira execução o sistema cria as regras e listas de exemplo em `data/app.db`.

Testes e auditoria do framework:

```bash
uv run pytest
```

```bash
uv run python audit_framework.py .
```

Resultado atual: 17 testes passando e 11/11 pilares do auditor. O `audit_framework.py` do framework tem um erro na função `colorize` (usa `ENDC` em vez de `Colors.ENDC`) e para antes do relatório; o resultado acima foi obtido sem alterar o arquivo, definindo `ENDC` antes de executá-lo.

## Capturas de tela

Com o sistema rodando em http://127.0.0.1:8000 e o Playwright instalado (`pip install playwright`, usa o Chrome da máquina):

```bash
python docs/prototipo/capturar_telas.py
```

O script percorre o fluxo (fila, detalhe, inclusão e desfazer, registro, painel, regras, tela de 1366×768) e salva em `docs/prototipo/screenshots/`. Rode com `data/app.db` limpo.

## Achados no extrato e na consulta do AGHU

1. Na consulta enviada, `... LIKE 'UNIDADE DE DIAGNÓSTICO POR IMAGEM%' OR ... LIKE '%UDI%' AND criado_em >= ...` aplica o filtro de 60 dias só à segunda condição (precedência do `AND`). A versão em `src/providers/sql/solicitacao/` usa parênteses.
2. `LIKE '%UDI%'` também casa com "FONOAUDIOLOGIA" (fono**audi**ologia): 72 itens de fonoaudiologia entram por acaso. Precisa confirmar se a Central marca esses exames.
3. Há exames repetidos para o mesmo paciente em solicitações diferentes (ex.: dois "Anatomopatológico - mama" no mesmo dia) e 14 itens sem prontuário.
4. O CSV do Drive vem com cada linha inteira entre aspas (aspas duplicadas dentro). Foi convertido para CSV comum antes de usar.

## Arquivos principais

- Backend: `src/controllers/fila_controller.py` (ordenação, combinações, painel), `src/routers/fila.py`, `src/routers/regras.py`, `src/models/agenda.py`, `src/providers/*/solicitacao_*`.
- Frontend: `frontend/src/views/Fila.vue`, `Painel.vue`, `Regras.vue`, `frontend/src/components/DetalhePaciente.vue`.
- Testes: `tests/test_prioridade.py`.
