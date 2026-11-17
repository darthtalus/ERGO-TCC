# Arquitetura e modelo de dados — ERGO v5

## 1. Camadas

```text
Navegador / cliente de sensor
        |
        v
URLs + views Django
        |
        +--> forms/serialização e validação
        +--> permissions.py
        +--> services.py (transações e estados)
        |
        v
Django ORM
        |
        +--> MySQL/MariaDB em operação
        +--> SQLite em memória na suíte isolada
```

A regra principal é: **views não decidem livremente o workflow**. Mudança de estado, conclusão e avaliação são centralizadas em `tasks/services.py`; autorização reutilizável fica em `tasks/permissions.py`.

## 2. Apps principais

| App | Responsabilidade |
|---|---|
| `accounts` | usuário, papéis globais e autenticação |
| `tasks` | tarefas, atribuições, avaliações, convites e links públicos |
| `user_aspects` | efetividade diária e histórico ABC |
| `dimensions`, `units`, `user_dimensions` | parametrização ergonômica |
| `upgrades` | análise, colaboração, revisão, modelos, recorrência e sensores |
| `pages` | páginas institucionais |

## 3. Entidades do núcleo

### `Task`

Descrição, estimativa, dificuldade 0–5, proprietário e data de criação. Não possui um estado único: o estado pertence à atribuição de cada executor.

### `TaskUser` (`task_assignment`)

Liga usuário, tarefa e papel:

- `EXECUTOR`: `DOING`, `PAUSED`, `CANCELED` ou `DONE`;
- `STAKEHOLDER`: sempre `NONE`.

Constraint única: tarefa + usuário + papel.

### `TaskRate` (`task_evaluation`)

- `SELF`: Ambiente, Cognição, Comportamento e Efetividade, todos 1–5;
- `STAKEHOLDER`: apenas Efetividade 1–5.

Constraint única: atribuição + avaliador + tipo. `created_at` identifica criação e `updated_at` a última atualização antes do fechamento do ciclo.

### Convites e compartilhamento

- `TaskInvitation`: convite por e-mail com expiração;
- `TaskShareLink`: token público revogável;
- `TaskJoinRequest`: solicitação externa, decisão e auditoria.

## 4. Entidades integradas

### `TaskReview`

Registro append-only de decisão. Campos principais: atribuição, revisor, status, comentário, ciclo, snapshot JSON e data.

### `TaskComment`

Comentário e anexo opcional. O arquivo usa armazenamento privado.

### `TaskStartChecklist`

Resposta preventiva por executor, score 0–6 e recomendações.

### `TaskTemplate` e `TaskChecklistItem`

Modelo reutilizável e itens operacionais copiados para a tarefa.

### `RecurringTaskRule` e `RecurringTaskOccurrence`

Regra com frequência/data âncora e registro idempotente de cada ocorrência.

### `SensorReading` e `SensorApiToken`

Leituras ambientais e credencial hashada por usuário para ingestão externa.

## 5. Invariantes do fluxo

- `DONE` só nasce junto com autoavaliação válida;
- stakeholder nunca possui estado operacional;
- executor não avalia/revisa a própria atribuição;
- revisão exige conclusão válida;
- devolução reabre para `DOING` e inicia novo ciclo;
- aprovação é final;
- revisão histórica não é reescrita;
- avaliação final não é alterada/apagada;
- ações críticas são transacionais e, quando necessário, bloqueiam linhas.

## 6. Consistência entre aplicação e banco

Há três camadas complementares:

1. **formulários/serialização** — mensagens amigáveis;
2. **serviços e permissões** — regra de negócio;
3. **constraints** — última barreira de integridade.

Validadores de modelo não substituem constraints, e constraints não substituem autorização.

## 7. Arquivos centrais

```text
tasks/models.py
tasks/forms.py
tasks/permissions.py
tasks/services.py
tasks/views.py
tasks/tests.py
upgrades/models.py
upgrades/forms.py
upgrades/services.py
upgrades/views.py
upgrades/tests.py
ergo/settings.py
ergo/test_settings.py
```

## 8. Migrações de integridade

- `tasks/0018_task_workflow_integrity.py`;
- `tasks/0019_taskrate_updated_at.py`;
- `upgrades/0002_security_workflow_and_validation.py`;
- `upgrades/0003_task_review_audit_snapshot.py`.

## 9. Diagramas

Consulte [`DIAGRAMAS.md`](DIAGRAMAS.md) e [`renamed-tables.md`](renamed-tables.md).
