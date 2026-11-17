# Fluxo de tarefas validado — ERGO v5

## 1. Unidade do fluxo

Uma `Task` descreve o trabalho. O estado pertence a cada `TaskUser` do tipo `EXECUTOR`. Assim, dois executores na mesma tarefa possuem ciclos independentes.

## 2. Papéis

- **Proprietário:** cria a tarefa, administra papéis, acompanha e pode avaliar/revisar outros executores.
- **Executor:** gerencia o próprio progresso, responde checklist e conclui com autoavaliação.
- **Stakeholder:** acompanha executores e registra avaliação/revisão.
- **Administrador:** possui alcance organizacional, mas não pode avaliar ou aprovar a própria atribuição.
- **Usuário externo:** vê apenas a página pública autorizada pelo token e pode solicitar participação.

## 3. Estados e transições

```text
DOING -> PAUSED | CANCELED
PAUSED -> DOING | CANCELED
CANCELED -> DOING
DOING ou PAUSED -> DONE somente via conclusão + autoavaliação
DONE -> DOING somente por revisão RETURNED
DONE + revisão APPROVED -> estado final
```

Reenvios do mesmo estado são idempotentes. `DONE` não aparece no formulário genérico de status.

## 4. Sequência completa

1. proprietário cria tarefa;
2. adiciona executores e stakeholders;
3. executor pode preencher checklist preventivo em `DOING`/`PAUSED`;
4. executor pausa, retoma ou cancela a própria atribuição;
5. executor conclui com notas inteiras 1–5 para Ambiente, Cognição, Comportamento e Efetividade;
6. a transação grava a autoavaliação e muda para `DONE`;
7. stakeholder registra Efetividade 1–5;
8. revisor pode marcar pendente, devolver ou aprovar;
9. devolução cria snapshot, remove avaliações de stakeholder do ciclo e volta a `DOING`;
10. executor corrige e conclui novamente;
11. stakeholder avalia o novo ciclo;
12. aprovação cria snapshot final e congela avaliações/revisões.

## 5. Separação de funções

O usuário nunca pode avaliar/revisar a própria atribuição de executor, mesmo quando também é proprietário, administrador ou stakeholder da tarefa. A fila de revisão deixa autoatribuições visíveis quando necessário, mas não as marca como pendentes para esse usuário.

## 6. Integridade transacional

As operações críticas usam `transaction.atomic` e bloqueio de linha com `select_for_update`:

- conclusão;
- avaliação e remoção de avaliação;
- revisão/devolução/aprovação;
- mudança de status;
- aceite de convite;
- decisão sobre solicitação pública;
- checklist pré-tarefa.

Uma avaliação inválida não altera o status. Uma corrida entre checklist e conclusão é serializada.

## 7. Ciclos e auditoria

Cada `TaskReview` armazena:

- número do ciclo;
- decisão;
- revisor;
- comentário;
- data;
- snapshot JSON da autoavaliação e das avaliações de stakeholders.

Revisões são append-only. Após `APPROVED`, o serviço impede atualizar/apagar avaliações e impede nova devolução.

## 8. Constraints

O banco impede duplicidade de papel e avaliação, notas fora da faixa, payload incompatível, tipo/estado incoerente e ciclo/revisão inválidos. Dados legados são normalizados pelas migrações antes das constraints.

## 9. Ações administrativas

O Django Admin não é um atalho para mudar o workflow:

- atribuições existentes têm campos de fluxo somente leitura;
- avaliações e revisões são somente leitura;
- exclusão de atribuições pelo Admin é bloqueada.

## 10. Evidência de validação

A validação é composta por:

- 43 testes automatizados;
- contrato estático do fluxo;
- validação de templates/traduções/migrações;
- verificação de documentação;
- roteiro manual de aceite.

Consulte [`RELATORIO_VALIDACAO_V5.md`](RELATORIO_VALIDACAO_V5.md).
