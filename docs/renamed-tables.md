# Nomes semânticos das tabelas

## Objetivo

O projeto usa `Meta.db_table` para manter nomes curtos e semânticos em inglês, evitando nomes automáticos como `tasks_taskrate`. As classes Python foram preservadas para compatibilidade.

## Tabelas do núcleo

| App | Modelo | Tabela |
|---|---|---|
| accounts | `CustomUser` | `user` |
| accounts | `CustomUserGroup` | `user_group` |
| accounts | `CustomUserPermission` | `user_permission` |
| dimensions | `Dimension` | `ergonomic_dimension` |
| units | `Unit` | `measurement_unit` |
| user_dimensions | `UserDimension` | `user_dimension_assignment` |
| user_aspects | `UserAspects` | `aspect_measurement` |
| user_aspects | `Effectiveness` | `daily_effectiveness` |
| user_aspects | `UserAspectHistory` | `measurement_history` |
| user_aspects | `DimensionUnit` | `dimension_unit_mapping` |
| user_aspects | `PredefinedAspect` | `aspect_template` |
| tasks | `Task` | `task` |
| tasks | `TaskUser` | `task_assignment` |
| tasks | `TaskRate` | `task_evaluation` |
| tasks | `TaskInvitation` | `task_invitation` |
| tasks | `TaskShareLink` | `task_share_link` |
| tasks | `TaskJoinRequest` | `task_join_request` |

## Tabelas da área de análises e fluxo

| App | Modelo | Tabela |
|---|---|---|
| upgrades | `TaskComment` | `task_comment` |
| upgrades | `TaskReview` | `task_review` |
| upgrades | `TaskTemplate` | `task_template` |
| upgrades | `RecurringTaskRule` | `recurring_task_rule` |
| upgrades | `RecurringTaskOccurrence` | `recurring_task_occurrence` |
| upgrades | `TaskStartChecklist` | `task_start_checklist` |
| upgrades | `TaskChecklistItem` | `task_checklist_item` |
| upgrades | `SensorReading` | `sensor_reading` |
| upgrades | `SensorApiToken` | `sensor_api_token` |

## Migrações de renomeação do núcleo

| App | Migração |
|---|---|
| accounts | `0009_alter_customuser_options_alter_customuser_table_and_more` |
| dimensions | `0002_alter_dimension_table` |
| tasks | `0016_alter_task_table_alter_taskinvitation_table_and_more` |
| units | `0002_alter_unit_table` |
| user_aspects | `0019_alter_dimensionunit_table_alter_effectiveness_table_and_more` |
| user_dimensions | `0002_alter_userdimension_table` |

As tabelas de `upgrades` foram criadas com nomes semânticos. As migrações `0002_security_workflow_and_validation` e `0003_task_review_audit_snapshot` acrescentam segurança, idempotência, ciclos e snapshots sem renomear as tabelas.

## Observações

- `TaskUser` continua sendo o nome da classe legada, embora represente uma atribuição e use a tabela `task_assignment`.
- `TaskRate` continua sendo o nome da classe, embora a tabela seja `task_evaluation`.
- `TaskRate.updated_at` foi acrescentado em `tasks.0019_taskrate_updated_at`; não altera o nome da tabela.
- `TaskReview` recebeu `cycle_number` e `evaluation_snapshot` em `upgrades.0003_task_review_audit_snapshot`.
- A tabela antiga de `TaskRating` foi removida por migração.
- Alterar um `db_table` exige migração e backup; não renomeie tabelas diretamente em produção sem planejar o estado do Django.
