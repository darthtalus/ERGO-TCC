# Testes e validação

## Suíte automatizada

A versão v5 contém:

- `tasks/tests.py`: 26 testes;
- `upgrades/tests.py`: 17 testes;
- total: 43 testes.

O banco de testes é SQLite em memória e não usa a `DATABASE_URL` real.

```powershell
python manage.py test tasks upgrades --settings=ergo.test_settings -v 2
```

## Cobertura funcional

Os testes verificam:

- criação, edição e normalização de papéis;
- bloqueio de usuário externo;
- ações POST-only;
- restrições de remoção com histórico;
- máquina de estados;
- conclusão somente pelo executor;
- atomicidade da autoavaliação;
- notas 1–5 e valores não numéricos;
- avaliação por stakeholder/proprietário/admin;
- separação de funções;
- fila correta para proprietário/admin;
- devolução, novo ciclo e aprovação;
- snapshots e ciclos de revisão;
- congelamento pós-aprovação;
- imutabilidade da revisão;
- convites idempotentes;
- privacidade da solicitação pública;
- constraints de banco;
- Kanban, checklist, anexos, sensores, recorrência e pseudonimização.

## Validadores estáticos

```powershell
python scripts/validate_task_workflow.py
python scripts/validate_upgrades_static.py
python scripts/validate_documentation_links.py
```

Eles verificam contratos que podem ser perdidos em refatorações: decorators, uso de serviços, constraints, migrações, traduções, privacidade, arquivos obrigatórios e links.

A verificação de higiene deve ser usada somente em uma cópia limpa destinada à distribuição:

```powershell
.\scripts\run_package_validation_windows.ps1
```

Ela rejeita deliberadamente `venv`, `.env`, backups SQL e outros artefatos locais.

## Validação completa

Windows:

```powershell
.\scripts\run_validation_windows.ps1
```

Linux/macOS:

```bash
./scripts/run_validation.sh
```

## Roteiro manual de aceite

Use contas diferentes: proprietário, executor, stakeholder e usuário externo.

1. criar tarefa e adicionar papéis;
2. confirmar que externo recebe 403 nas rotas internas;
3. executor preencher checklist;
4. pausar e retomar;
5. tentar nota inválida e confirmar que não conclui;
6. concluir com notas válidas;
7. confirmar que outro executor não consegue concluir;
8. stakeholder avaliar;
9. devolver e confirmar remoção da avaliação anterior;
10. concluir e avaliar novamente;
11. aprovar;
12. tentar alterar/apagar avaliação e devolver após aprovação;
13. confirmar bloqueio e snapshot final;
14. conferir histórico, Kanban, dashboard e relatório;
15. testar link público sem nomes/status da solicitação.

## Critério de aprovação

O fluxo é aceito quando:

- todos os comandos retornam código 0;
- os 43 testes passam;
- `makemigrations --check --dry-run` não detecta diferenças;
- o roteiro manual não produz transições ou acessos indevidos.

## Limite do relatório do pacote

O relatório distingue validação estática executada no empacotamento de testes Django que devem ser repetidos no ambiente instalado. Consulte [`RELATORIO_VALIDACAO_V5.md`](RELATORIO_VALIDACAO_V5.md).
