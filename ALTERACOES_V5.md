# Alterações da versão v5

Data: **04/08/2026**

Esta versão consolida as correções do fluxo original de tarefas e das funcionalidades integradas de análise e colaboração.

## 1. Autorização centralizada

- criação sempre vincula a tarefa ao usuário autenticado;
- somente proprietário, `ADMIN`, `SUPERADMIN` ou superusuário Django podem editar, excluir e administrar papéis;
- executor altera apenas a própria atribuição, salvo ações administrativas não finais;
- somente o executor atribuído pode concluir e enviar autoavaliação;
- o executor nunca pode atuar como stakeholder/revisor da própria atribuição;
- proprietários, stakeholders atribuídos e administradores podem avaliar outros executores;
- a fila de avaliação inclui tarefas do proprietário e do stakeholder, mas nunca oferece autoavaliação como pendência;
- superusuário criado com `createsuperuser` funciona sem editar manualmente o campo `role`.

## 2. Máquina de estados única

As telas antigas e o Kanban agora utilizam `tasks/services.py`.

Transições permitidas:

```text
DOING     -> DOING, PAUSED, CANCELED
PAUSED    -> PAUSED, DOING, CANCELED
CANCELED  -> CANCELED, DOING
DONE      -> DONE
```

`DONE` só é alcançado pelo serviço de conclusão, após validar a autoavaliação. A devolução formal é a única operação que reabre `DONE` para `DOING`.

## 3. Conclusão e avaliações

- formulários aceitam apenas inteiros de 1 a 5;
- a autoavaliação e a mudança para `DONE` ocorrem na mesma transação;
- uma falha nunca deixa a atribuição concluída sem avaliação;
- avaliações são únicas por atribuição, avaliador e tipo;
- avaliação de stakeholder exige atribuição concluída e autoavaliação válida;
- `TaskRate.updated_at` registra a última atualização do ciclo;
- após aprovação final, avaliações não podem ser alteradas nem apagadas.

## 4. Revisão por ciclos e auditoria

- cada revisão recebe `cycle_number`;
- cada decisão armazena `evaluation_snapshot` com o contexto da tarefa/atribuição, a autoavaliação e as avaliações de stakeholders daquele momento;
- registros `TaskReview` são imutáveis: correções devem ser uma nova decisão;
- uma devolução remove avaliações de stakeholder do ciclo corrente e reabre a execução;
- uma aprovação é final;
- migração de dados atribui ciclos possíveis a revisões antigas; snapshots históricos impossíveis de reconstruir permanecem vazios.

## 5. Papéis, convites e participação

- papéis duplicados são impedidos no formulário e no banco;
- remoção ocorre somente por `POST` e é bloqueada quando há histórico;
- convites usam confirmação por `GET` e aceite idempotente por `POST`;
- decisões sobre solicitações públicas são transacionais e idempotentes;
- a página pública não revela o status de uma solicitação por parâmetro de e-mail;
- nomes de participantes ficam ocultos em links públicos por padrão.

## 6. Checklists, comentários e anexos

- checklist pré-tarefa só pode ser respondido pelo executor durante `DOING` ou `PAUSED`;
- o estado é travado durante a gravação para evitar corrida com conclusão;
- checklists de modelos são copiados para a tarefa;
- comentários exigem acesso à tarefa;
- anexos são validados, armazenados em área privada e baixados por rota autorizada.

## 7. Django Admin

- atribuições existentes são somente leitura no Admin;
- avaliações e revisões são registros de auditoria somente leitura;
- exclusão de tarefas e atribuições pelo Admin foi bloqueada para impedir desvio das regras da aplicação;
- a exclusão pela interface é recusada quando a tarefa já possui avaliações, revisões, checklists respondidos, comentários ou checklist operacional concluído;
- exclusão e criação de comentários usam bloqueios transacionais para evitar perda de histórico em acessos concorrentes.

## 8. Integridade do banco

Constraints garantem:

- uma combinação única de tarefa, usuário e papel;
- tipos e estados válidos;
- stakeholder sempre com status `NONE`;
- notas entre 1 e 5;
- payload ABC obrigatório para autoavaliação e ausente para stakeholder;
- uma avaliação por atribuição/avaliador/tipo;
- status e ciclo válidos em revisões.

## 9. Testes e validação

O pacote contém:

- **26 testes** no app `tasks`;
- **17 testes** no app `upgrades`;
- **43 testes de regressão no total**;
- validador estático do contrato do fluxo;
- validador de templates, traduções, migrações e regressões;
- validador dos links da documentação;
- script único para Windows e Linux.

## 10. Documentação

Foram atualizados README, instalação, arquitetura, modelo de dados, fluxo, rotas e permissões, segurança, APIs, migração, testes, internacionalização, operação e limites teóricos. O relatório de validação deixa explícito o que foi executado no ambiente de empacotamento e o que deve ser repetido no ambiente de destino.


## Ajustes complementares v5.1

- tradução de estados e rótulos PT-BR pendentes;
- constraint de banco para dificuldade de tarefas e modelos no intervalo de 0 a 5;
- migrações com normalização segura de dados legados;
- separação entre validação local e higiene do pacote de distribuição.
