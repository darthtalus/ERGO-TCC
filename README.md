# ERGO — avaliação ergonômica, efetividade e fluxo de tarefas

> **Versão v5.1 — fluxo protegido, consistência de banco e validação local corrigida — 04/08/2026.**

Revisão consolidada para o TCC em 17/11/2026: três correções complementares, com 48 testes automatizados aprovados no ambiente local Windows. Veja o [registro de validação final](docs/VALIDACAO_FINAL_TCC.md).

O ERGO é uma aplicação Django para gerenciamento de tarefas e acompanhamento da efetividade humana sob uma perspectiva ergonômica. A aplicação relaciona tarefas, papéis colaborativos, autoavaliações, avaliações de stakeholders e registros das dimensões Ambiente/Acesso, Cognição e Comportamento.

Este pacote é **limpo**: não contém banco preenchido, dump `ergo.sql`, anexos, arquivo `.env`, ambiente virtual nem dados pessoais.

## O que existe nesta versão

### Fluxo principal de tarefas

- criação e edição restritas ao proprietário ou administrador;
- papéis de **Executor** e **Stakeholder**;
- estados por atribuição de executor: `DOING`, `PAUSED`, `CANCELED` e `DONE`;
- conclusão somente pelo executor atribuído e sempre acompanhada de autoavaliação 1–5;
- avaliação de stakeholder somente após conclusão válida;
- devolução para ajustes, nova conclusão e aprovação final;
- avaliações e revisões congeladas após aprovação;
- histórico por ciclo com cópia imutável das avaliações;
- comentários, anexos protegidos e checklists;
- convites, links públicos e solicitações de participação;
- Kanban usando as mesmas regras do fluxo principal.

### Análises e recursos complementares

- dashboard pessoal e organizacional;
- gráficos de linha, barras, rosca, histograma, dispersão e dia da semana;
- recomendações heurísticas;
- comparação entre autoavaliação e stakeholder;
- modelos e tarefas recorrentes;
- leituras ambientais e API de sensores;
- relatório PDF e exportação CSV pseudonimizada;
- interface em Português do Brasil e Inglês.

## Máquina de estados

O status pertence à atribuição de cada executor, não à tarefa inteira.

```text
DOING ──► PAUSED ──► DOING
  │          │
  └──────► CANCELED ──► DOING
  │
  └── autoavaliação válida ──► DONE
                                  │
                                  ├── devolução ──► DOING
                                  └── aprovação ──► FINAL
```

`DONE` não pode ser definido por um campo livre ou pelo Kanban. Apenas o serviço transacional de conclusão cria/atualiza a autoavaliação e muda o estado. Após uma revisão `APPROVED`, a atribuição permanece final e suas avaliações não podem ser alteradas ou apagadas pela interface.

## Instalação rápida no Windows

Consulte [`RODAR_NO_WINDOWS.md`](RODAR_NO_WINDOWS.md). Resumo:

```powershell
py -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Ajuste `DATABASE_URL` no `.env` antes de executar as migrações.

## Validar o projeto

No PowerShell:

```powershell
.\scripts\run_validation_windows.ps1
```

Ou manualmente:

```powershell
python scripts/validate_task_workflow.py
python scripts/validate_upgrades_static.py
python scripts/validate_documentation_links.py
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test tasks upgrades --settings=ergo.test_settings -v 2
```

A suíte utiliza SQLite em memória e não toca no banco MySQL configurado no `.env`.

A higiene do pacote deve ser executada apenas sobre uma cópia limpa, antes de criar `venv`, `.env` ou backups:

```powershell
.\scripts\run_package_validation_windows.ps1
```

## Migrações relevantes da v5

- `tasks.0018_task_workflow_integrity`: normalização e constraints do fluxo;
- `tasks.0019_taskrate_updated_at`: timestamp da última atualização das avaliações;
- `tasks.0020_task_difficulty_constraint`: normalização legada e constraint de dificuldade 0–5;
- `upgrades.0002_security_workflow_and_validation`: segurança das extensões;
- `upgrades.0003_task_review_audit_snapshot`: ciclo, snapshot e constraints das revisões;
- `upgrades.0004_task_template_difficulty_constraint`: constraint de dificuldade 0–5 nos modelos de tarefa.

Faça backup do banco antes de atualizar uma instalação existente.

## Segurança e privacidade

- alterações de estado são `POST` e protegidas por CSRF;
- autorização é verificada no servidor;
- superusuários Django são reconhecidos mesmo sem promoção manual do campo `role`;
- anexos são servidos por rota autenticada e armazenamento privado;
- registros de avaliação e revisão são somente leitura no Django Admin;
- links públicos ocultam nomes de participantes por padrão;
- o status de uma solicitação não é revelado apenas pela posse do e-mail;
- a exportação adicional é pseudonimizada, não anonimizada de forma irreversível.

## Modelo teórico

O ERGO é inspirado no modelo ABC de efetividade digital e permite registrar fatores ambientais/de acesso, cognitivos e comportamentais. Recomendações, ranking heurístico, score de risco, Kanban e workflow de aprovação são extensões operacionais e **não constituem, por si só, instrumentos científicos validados ou diagnóstico ergonômico**.

Consulte [`docs/MODELO_TEORICO_E_LIMITES.md`](docs/MODELO_TEORICO_E_LIMITES.md).

## Documentação

O índice completo está em [`docs/INDICE_DOCUMENTACAO.md`](docs/INDICE_DOCUMENTACAO.md).

Documentos principais:

- [`ALTERACOES_V5.md`](ALTERACOES_V5.md) — lista detalhada das mudanças;
- [`docs/FLUXO_DE_TAREFAS_VALIDADO.md`](docs/FLUXO_DE_TAREFAS_VALIDADO.md) — regras do fluxo;
- [`docs/RELATORIO_VALIDACAO_V5.md`](docs/RELATORIO_VALIDACAO_V5.md) — evidências e limites da validação;
- [`docs/ROTAS_E_PERMISSOES.md`](docs/ROTAS_E_PERMISSOES.md) — matriz de autorização;
- [`docs/TESTES_E_VALIDACAO.md`](docs/TESTES_E_VALIDACAO.md) — execução dos testes;
- [`docs/MIGRACAO_E_ATUALIZACAO.md`](docs/MIGRACAO_E_ATUALIZACAO.md) — atualização segura;
- [`docs/SEGURANCA_PRIVACIDADE_E_LGPD.md`](docs/SEGURANCA_PRIVACIDADE_E_LGPD.md) — controles e responsabilidades.

## Stack

- Python 3.10–3.14;
- Django 5.2 LTS;
- MySQL/MariaDB em operação normal;
- SQLite em memória para testes isolados;
- templates Django, Bootstrap, JavaScript e Chart.js;
- Matplotlib/Pandas para análises e PDF.

## Origem

Projeto desenvolvido no CCSA/UFPB, concebido pelo pesquisador Dr. Carlo Gabriel Porto Bellini, com desenvolvimento full-stack atribuído no projeto original a Leonardo Américo Bezerra Viana.
