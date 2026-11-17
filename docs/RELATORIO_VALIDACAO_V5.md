# Relatório de validação — ERGO v5

Data de construção do pacote: **04/08/2026**.

## 1. Escopo

A v5 corrige o fluxo original de tarefas, integra Kanban/colaboração ao mesmo contrato e entrega documentação e testes para:

```text
criar -> atribuir -> executar -> pausar/retomar -> checklist
-> concluir com autoavaliação -> avaliar -> devolver
-> concluir novamente -> avaliar -> aprovar -> congelar
```

## 2. Validações executadas no ambiente de empacotamento

| Verificação | Resultado |
|---|---|
| compilação dos arquivos Python | aprovado |
| validação estrutural dos templates | aprovado |
| catálogo PT-BR compilado | aprovado |
| contrato estático do workflow | aprovado |
| regressões estáticas das funcionalidades integradas | aprovado |
| links relativos da documentação | aprovado |
| diagramas Graphviz regenerados | aprovado |
| higiene do arquivo final | aprovado |
| integridade do ZIP | aprovado |

## 3. Suíte automatizada entregue

- `tasks/tests.py`: 26 testes;
- `upgrades/tests.py`: 17 testes;
- total: 43.

Comando:

```powershell
python manage.py test tasks upgrades --settings=ergo.test_settings -v 2
```

`ergo/test_settings.py` usa SQLite em memória, e-mail em memória, hasher rápido e stubs apenas no ambiente de testes. Não acessa o MySQL configurado no `.env`.

## 4. Cobertura principal

- edição/papéis restritos;
- POST-only e CSRF;
- constraints e duplicidades;
- estados e transições;
- conclusão atômica;
- exclusão serializada e bloqueada após histórico de workflow;
- notas inválidas;
- separação de funções;
- proprietário/stakeholder/admin;
- devolução e ciclos;
- snapshots e imutabilidade;
- congelamento após aprovação;
- checklist e corrida com conclusão;
- privacidade dos links públicos;
- Kanban, anexos, recorrência, sensores e pseudonimização.

## 5. Limite do ambiente de construção

O ambiente usado para construir este ZIP não possui Django instalado e não teve acesso a uma fonte de pacotes capaz de instalar as dependências. Por isso, **a suíte Django não foi executada nesse ambiente**. Não seria correto declarar que os 43 testes passaram aqui.

Foram executados os validadores independentes de Django, compilação e verificações de pacote. A suíte deve ser executada no computador de destino após `pip install -r requirements.txt`.

## 6. Critério para declarar o fluxo validado no ambiente de destino

Execute:

```powershell
.\scripts\run_validation_windows.ps1
```

O fluxo é aceito quando:

1. todos os comandos terminam com código 0;
2. os 43 testes mostram `OK`;
3. `makemigrations --check --dry-run` não encontra diferenças;
4. o roteiro manual abaixo passa com contas separadas.

## 7. Roteiro manual

1. criar proprietário, executor, stakeholder e externo;
2. criar tarefa e atribuir papéis;
3. confirmar bloqueios do externo;
4. preencher checklist em execução;
5. pausar/retomar;
6. tentar conclusão inválida e confirmar estado inalterado;
7. concluir com notas 1–5;
8. confirmar que terceiro não conclui;
9. stakeholder avaliar;
10. devolver e confirmar novo ciclo;
11. concluir e avaliar novamente;
12. aprovar;
13. tentar alterar/apagar avaliação ou reescrever revisão;
14. confirmar bloqueio final e snapshot;
15. verificar histórico, Kanban, painel, PDF e anexo;
16. abrir link público e confirmar nomes/status ocultos.

## 8. Conclusão

O pacote corrige e protege estaticamente o contrato do fluxo, contém testes automatizados e documentação de aceite. A homologação final deve registrar o resultado da suíte e do roteiro manual no ambiente instalado. Não use em produção se qualquer etapa falhar.


## Ajustes v5.1

- traduções PT-BR pendentes foram completadas;
- tarefas e modelos de tarefa receberam constraints de dificuldade entre 0 e 5;
- a validação local foi separada da higiene de uma cópia limpa para distribuição.
