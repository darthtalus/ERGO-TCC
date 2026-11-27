# ERGO — avaliação ergonômica, efetividade e fluxo de tarefas

> **Base evoluída de desenvolvimento — consolidação técnica para o TCC em 26/11/2026.**

A primeira versão destinada ao ambiente de produção encontra-se em processo de homologação.

Validação consolidada em 26/11/2026: 49 testes automatizados aprovados em 2,076 segundos no ambiente Windows, utilizando SQLite em memória. A suíte é compartilhada pelas duas frentes do projeto. Commit do código validado: `9f3b1f3`; commit do registro de validação: `e1e13b3`. Veja o [registro de validação final](docs/VALIDACAO_FINAL_TCC.md).

O ERGO é uma aplicação Django para gerenciamento de tarefas e acompanhamento da efetividade humana sob uma perspectiva ergonômica. A aplicação relaciona tarefas, papéis colaborativos, autoavaliações, avaliações de stakeholders e registros das dimensões Ambiente/Acesso, Cognição e Comportamento.

O pacote consolidado foi preparado sem banco preenchido, dump `ergo.sql`, anexos, arquivo `.env` ou ambiente virtual. A eventual disponibilização pública do repositório depende de alinhamento com os responsáveis pelo projeto e de revisão de segurança e privacidade.

## Funcionalidades da base evoluída

### Fluxo principal de tarefas

- criação e edição restritas ao proprietário ou administrador;
- papéis de **Executor** e **Stakeholder**;
- estados por atribuição de executor: `DOING`, `PAUSED`, `CANCELED` e `DONE`;
- conclusão somente pelo executor atribuído e sempre acompanhada de autoavaliação 1–5;
- avaliação de stakeholder somente após conclusão válida;
- devolução para ajustes, nova conclusão e aprovação final;
- avaliações e revisões congeladas após aprovação pelo fluxo normal da aplicação;
- histórico por ciclo com cópia imutável das avaliações no fluxo normal;
- comentários, anexos protegidos e checklists;
- convites, links públicos e solicitações de participação;
- Kanban usando as mesmas regras do fluxo principal;
- listagem com associação individual entre executor e status.

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

DOING ou PAUSED ── autoavaliação válida ──► DONE
                                             │
                                             ├── devolução ──► DOING
                                             └── aprovação ──► DONE (APPROVED)
```

`DONE` não pode ser definido por um campo livre ou pelo Kanban. Apenas o serviço transacional de conclusão cria/atualiza a autoavaliação e muda o estado. Após uma revisão `APPROVED`, a atribuição permanece em `DONE` e suas avaliações não podem ser alteradas ou apagadas pela interface. A aprovação é uma decisão de revisão, não um novo estado operacional da atribuição.

## Instalação rápida no Windows

Consulte [`RODAR_NO_WINDOWS.md`](RODAR_NO_WINDOWS.md). Resumo para uma nova instalação:

```powershell
py -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Ajuste `DATABASE_URL` no `.env` antes de executar as migrações. Consulte também a seção de migrações abaixo, especialmente ao atualizar uma instalação existente.

```powershell
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

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

A suíte de testes indicada utiliza SQLite em memória e não toca no banco MySQL configurado no `.env`. Seus resultados não equivalem à homologação em produção, a um teste de carga ou à validação das migrações no MySQL operacional.

A higiene do pacote deve ser executada apenas sobre uma cópia limpa, antes de criar `venv`, `.env` ou backups:

```powershell
.\scripts\run_package_validation_windows.ps1
```

## Migrações relevantes da evolução

- `tasks.0018_task_workflow_integrity`: normalização e constraints do fluxo;
- `tasks.0019_taskrate_updated_at`: timestamp da última atualização das avaliações;
- `tasks.0020_task_difficulty_constraint`: normalização legada e constraint de dificuldade 0–5;
- `upgrades.0002_security_workflow_and_validation`: segurança das extensões;
- `upgrades.0003_task_review_audit_snapshot`: ciclo, snapshot e constraints das revisões;
- `upgrades.0004_task_template_difficulty_constraint`: constraint de dificuldade 0–5 nos modelos de tarefa;
- `accounts.0009`: correção da migração de usuários e permissões, integrada em 26/11/2026. Sua execução no banco MySQL operacional ainda requer verificação específica.

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

O ERGO é inspirado no modelo ABC de efetividade digital (Access, Behavior e Cognition), operacionalizado na aplicação pelas dimensões Ambiente, Comportamento e Cognição. O acompanhamento diário permite parametrizar aspectos com diferentes unidades de medida e registrar separadamente a percepção geral de efetividade em uma escala de 1 a 5. Na conclusão de uma atribuição, o executor informa as três dimensões e a efetividade; o interessado avalia a efetividade da entrega. A nota geral não é calculada automaticamente como média das dimensões.

Recomendações, ranking heurístico, score de risco, Kanban e workflow de aprovação são extensões operacionais e **não constituem, por si só, instrumentos científicos validados ou diagnóstico ergonômico**.

Consulte [`docs/MODELO_TEORICO_E_LIMITES.md`](docs/MODELO_TEORICO_E_LIMITES.md).

## Documentação

Os nomes históricos dos arquivos foram preservados e não representam versões oficiais de produção. O índice completo está em [`docs/INDICE_DOCUMENTACAO.md`](docs/INDICE_DOCUMENTACAO.md).

Documentos principais:

- [`docs/VALIDACAO_FINAL_TCC.md`](docs/VALIDACAO_FINAL_TCC.md) — registro atualizado da validação;
- [`ALTERACOES_V5.md`](ALTERACOES_V5.md) — lista histórica detalhada das mudanças;
- [`docs/FLUXO_DE_TAREFAS_VALIDADO.md`](docs/FLUXO_DE_TAREFAS_VALIDADO.md) — regras do fluxo;
- [`docs/RELATORIO_VALIDACAO_V5.md`](docs/RELATORIO_VALIDACAO_V5.md) — evidências e limites da validação anterior;
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
