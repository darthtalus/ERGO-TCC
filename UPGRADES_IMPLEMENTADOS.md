# ERGO — funcionalidades integradas de análise e fluxo

> O nome funcional exibido na interface é **Análises e fluxo de trabalho** em português e **Ergonomic analysis and workflow** em inglês. O nome técnico do app Django continua `upgrades` apenas por compatibilidade de código, migrações e URLs.

## 1. Integração com o núcleo

A área adicional não cria um segundo fluxo de tarefas. Ela reutiliza os modelos e serviços do núcleo:

- `Task` — descrição da tarefa;
- `TaskUser` — atribuição por usuário e papel;
- `TaskRate` — autoavaliação e avaliação de stakeholder;
- `tasks/services.py` — máquina de estados e regras transacionais;
- `tasks/permissions.py` — autorização no servidor.

Kanban, colaboração e revisão chamam o mesmo contrato do fluxo principal. As regras completas estão em [`docs/FLUXO_DE_TAREFAS_VALIDADO.md`](docs/FLUXO_DE_TAREFAS_VALIDADO.md).

## 2. Painel analítico

Rota: `/upgrades/`.

O painel possui dois escopos:

- **Pessoal:** registros do usuário e tarefas em que participa;
- **Organização:** somente para `ADMIN`, `SUPERADMIN` ou superusuário Django.

Apresenta efetividade diária, médias ABC, estados das atribuições, divergências entre avaliações, recomendações baseadas em regras, leituras ambientais e gráficos. O escopo solicitado é revalidado no backend; um usuário comum não obtém dados globais alterando a URL.

## 3. Visualizações

A API `/upgrades/api/charts/` alimenta:

- linha temporal da efetividade e dimensões ABC;
- barras das médias ABC;
- rosca dos estados das atribuições de executor;
- efetividade média por dia da semana;
- histograma de dificuldade;
- dispersão dificuldade × efetividade;
- distribuição dos papéis visíveis.

Os gráficos são descritivos. Eles não comprovam causalidade nem substituem validação estatística.

## 4. Resumo e recomendações

O resumo é produzido por regras locais, sem API externa de IA. Entre os gatilhos estão ausência de registros, queda recente, média baixa, tarefa difícil em andamento e leituras ambientais fora das faixas heurísticas do software.

Essas mensagens são indicadores exploratórios, não diagnóstico clínico, laudo ou recomendação normativa.

## 5. Kanban

Rota: `/upgrades/kanban/`.

Cada cartão representa uma **atribuição de executor**. Uma tarefa com dois executores gera dois cartões, pois os estados são independentes.

Podem alterar o estado:

- o próprio executor;
- o proprietário da tarefa;
- administrador, superadministrador ou superusuário.

`DONE` não pode ser selecionado pelo Kanban. A conclusão exige o serviço transacional e autoavaliação válida.

## 6. Colaboração e anexos

Rota: `/upgrades/tasks/<task_id>/collaboration/`.

Inclui:

- comentários de até 2.000 caracteres;
- anexos com extensão e tamanho validados;
- download por rota autenticada e autorizada;
- checklist operacional copiado de modelo;
- checklist ergonômico preventivo;
- revisões por ciclo;
- histórico recente.

Os arquivos ficam em armazenamento privado (`PRIVATE_MEDIA_ROOT`) e não devem ser expostos diretamente pelo servidor web.

## 7. Checklist preventivo

Somente o executor daquela atribuição pode responder, e apenas em `DOING` ou `PAUSED`. O backend bloqueia a linha durante a gravação para evitar corrida com a conclusão.

O score 0–6 conta respostas desfavoráveis sobre ambiente, iluminação, ruído, fadiga, clareza e critérios de aceite. É uma regra interna do produto, não escala clínica validada.

## 8. Revisão, devolução e aprovação

A revisão exige atribuição de executor em `DONE` com autoavaliação válida. Revisor autorizado: proprietário, stakeholder atribuído ou administrador, nunca o próprio executor daquela atribuição.

- `PENDING`: registra acompanhamento sem encerrar;
- `RETURNED`: cria snapshot, remove avaliações de stakeholder do ciclo e volta a `DOING`;
- `APPROVED`: cria snapshot final e congela avaliações e revisões posteriores.

Cada decisão é append-only, possui `cycle_number` e `evaluation_snapshot`.

## 9. Modelos e checklist operacional

Rota: `/upgrades/templates/`.

O usuário cria modelos com descrição, estimativas, dificuldade 0–5 e um item de checklist por linha. Ao gerar a tarefa, os itens são copiados para `TaskChecklistItem` e deixam de depender do texto do modelo.

## 10. Recorrência

Rota: `/upgrades/recurring/`.

Frequências diária, semanal e mensal. A mensal usa calendário e preserva o dia âncora quando possível. `RecurringTaskOccurrence` possui restrição única por regra/data, tornando a geração idempotente.

Comando:

```bash
python manage.py generate_recurring_tasks
```

Em produção, esse comando precisa ser agendado externamente.

## 11. Sensores

Rota: `/upgrades/sensors/`.

Registra temperatura, umidade, ruído, luminosidade, qualidade do ar, origem e observação. O POST externo usa chave dedicada; a chave completa aparece uma vez e o banco mantém apenas prefixo e hash SHA-256.

Consulte [`docs/API_E_INTEGRACOES.md`](docs/API_E_INTEGRACOES.md).

## 12. Relatórios e exportações

- `/upgrades/report/pdf/` — relatório exploratório com métricas e gráficos;
- `/upgrades/report/pseudonymized-csv/` — CSV pseudonimizado;
- `/upgrades/report/anonymized-csv/` — alias legado, mantido por compatibilidade.

A pseudonimização não garante anonimato irreversível.

## 13. APIs

Com sessão Django e escopo revalidado:

```text
GET /upgrades/api/tasks/
GET /upgrades/api/effectiveness/
GET /upgrades/api/recommendations/
GET /upgrades/api/charts/
```

Sensores:

```text
GET  /upgrades/api/sensors/   # sessão ou chave
POST /upgrades/api/sensors/   # chave dedicada obrigatória
```

## 14. Limites

- recomendações e scores são heurísticos;
- não há OAuth/JWT para as APIs de leitura;
- não há Celery embutido;
- anexos exigem operação segura do diretório privado;
- gráficos não equivalem a inferência estatística;
- o modelo ABC e suas limitações estão documentados em [`docs/MODELO_TEORICO_E_LIMITES.md`](docs/MODELO_TEORICO_E_LIMITES.md).
