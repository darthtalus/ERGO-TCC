# Rotas e permissões — ERGO v5

> Os caminhos abaixo são relativos ao domínio da aplicação. A autorização é verificada no backend; ocultar um botão não é controle de segurança.

## 1. Fluxo principal

| Rota | Método | Regra |
|---|---:|---|
| `/tasks/` | GET | usuário autenticado; conteúdo filtrado pelo vínculo |
| `/tasks/createdbyme` | GET | proprietário vê suas tarefas; perfil privilegiado pode ver escopo ampliado |
| `/tasks/stakeholder` | GET | fila de tarefas que o usuário pode avaliar/revisar |
| `/tasks/new` | GET/POST | usuário autenticado; o proprietário é sempre `request.user` |
| `/tasks/edit/<task_id>/update` | GET/POST | proprietário, `ADMIN`, `SUPERADMIN` ou superusuário |
| `/tasks/delete/<task_id>` | POST | proprietário ou perfil privilegiado |
| `/tasks/roles/<task_id>` | GET | proprietário ou perfil privilegiado |
| `/tasks/roles/<task_id>/role-new` | GET/POST | proprietário ou perfil privilegiado; tarefa vem da URL, não do cliente |
| `/tasks/roles/<assignment_id>/delete` | POST | proprietário ou perfil privilegiado; bloqueado quando existe histórico |
| `/tasks/change` | POST | executor da atribuição, proprietário ou perfil privilegiado; nunca define `DONE` |
| `/tasks/done` | POST | somente o executor correspondente |
| `/tasks/stakeholder-evaluate` | POST | proprietário, stakeholder atribuído ou perfil privilegiado; nunca o próprio executor |
| `/tasks/stakeholder-clear-evaluate/<taskuser_id>` | POST | apenas o autor da avaliação; bloqueado após aprovação final |
| `/tasks/history/<task_id>` | GET | proprietário, participante ou perfil privilegiado |
| `/tasks/history/send-reminder/<taskuser_id>` | POST | proprietário, stakeholder ou perfil privilegiado; somente para executor não concluído |

## 2. Convites e compartilhamento

| Rota | Método | Regra |
|---|---:|---|
| `/tasks/invite/<token>/` | GET | mostra confirmação; não altera o banco |
| `/tasks/invite/<token>/` | POST | usuário autenticado com e-mail compatível; aceite idempotente |
| `/tasks/share/<task_id>` | POST | proprietário ou perfil privilegiado; ativa, desativa ou regenera token |
| `/tasks/public/<token>/` | GET | público, apenas token ativo |
| `/tasks/public/<token>/` | POST | público, cria uma solicitação genérica protegida por CSRF |
| `/tasks/join-requests/<task_id>` | GET/POST | proprietário ou perfil privilegiado; decisão transacional/idempotente |

A página pública não revela o status por e-mail e oculta nomes por padrão. `PUBLIC_SHARE_SHOW_PARTICIPANT_NAMES=True` é opt-in de implantação.

## 3. Colaboração integrada

| Rota | Método | Regra |
|---|---:|---|
| `/upgrades/` | GET | autenticado; escopo pessoal ou organizacional autorizado |
| `/upgrades/kanban/` | GET | atribuições visíveis |
| `/upgrades/kanban/update/` | POST | mesmas regras de `/tasks/change`; não conclui |
| `/upgrades/tasks/<task_id>/collaboration/` | GET | proprietário, participante ou perfil privilegiado |
| `/upgrades/tasks/<task_id>/comment/` | POST | usuário com acesso à tarefa |
| `/upgrades/comments/<comment_id>/attachment/` | GET | usuário com acesso à tarefa; download privado |
| `/upgrades/assignments/<taskuser_id>/checklist/` | POST | executor correspondente, apenas em `DOING`/`PAUSED` |
| `/upgrades/assignments/<taskuser_id>/review/` | POST | proprietário, stakeholder ou perfil privilegiado; nunca o executor correspondente |
| `/upgrades/checklist-items/<item_id>/toggle/` | POST | proprietário, executor da tarefa ou perfil privilegiado |

## 4. Revisão

- exige atribuição do tipo `EXECUTOR` em `DONE`;
- exige autoavaliação válida;
- aprovação exige avaliação de stakeholder atribuído quando a tarefa possui stakeholders;
- `RETURNED` reabre para `DOING` e inicia novo ciclo;
- `APPROVED` torna o fluxo final;
- revisões são append-only e avaliações finais não podem ser alteradas/apagadas.

## 5. Modelos, recorrência e sensores

| Rota | Método | Regra |
|---|---:|---|
| `/upgrades/templates/` | GET/POST | usuário autenticado; somente seus modelos |
| `/upgrades/templates/<id>/create-task/` | POST | proprietário do modelo |
| `/upgrades/recurring/` | GET/POST | usuário autenticado; somente suas regras |
| `/upgrades/recurring/run-due/` | POST | usuário autenticado; gera suas ocorrências vencidas |
| `/upgrades/sensors/` | GET/POST | usuário autenticado; somente suas leituras |
| `/upgrades/sensors/api-key/generate/` | POST | usuário autenticado |
| `/upgrades/sensors/api-key/revoke/` | POST | usuário autenticado |

## 6. Relatórios e APIs

| Rota | Método | Autenticação |
|---|---:|---|
| `/upgrades/report/pdf/` | GET | sessão Django |
| `/upgrades/report/pseudonymized-csv/` | GET | sessão Django |
| `/upgrades/api/tasks/` | GET | sessão Django |
| `/upgrades/api/effectiveness/` | GET | sessão Django |
| `/upgrades/api/recommendations/` | GET | sessão Django |
| `/upgrades/api/charts/` | GET | sessão Django |
| `/upgrades/api/sensors/` | GET | sessão ou chave de sensor |
| `/upgrades/api/sensors/` | POST | chave de sensor obrigatória |

## 7. Perfis privilegiados

São reconhecidos como privilegiados:

- `role=ADMIN`;
- `role=SUPERADMIN`;
- `is_superuser=True` do Django.

Mesmo um perfil privilegiado não pode avaliar ou revisar sua própria atribuição de executor.
