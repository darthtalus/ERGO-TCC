# Changelog

## v5.1 — revisão de validação do TCC (17/11/2026)

- Correção de duplicidade na listagem do proprietário.
- Identificação de tarefas sem executor e ocultação de ações de avaliação após aprovação.
- Histórico por ciclo com as avaliações registradas e respectivos horários; tradução de campos e mensagens.
- Ampliação da suíte para 48 testes (30 de tarefas e 18 de funcionalidades integradas).
- Empacotamento sem banco, credenciais ou estáticos coletados; preservação dos estáticos-fonte em `ergo/static/`.

## v5.1.0 — 04/08/2026

### Consistência e validação

- traduções PT-BR pendentes completadas, incluindo `Pending` e `Rejected`;
- constraints de banco para dificuldade 0–5 em tarefas e modelos;
- migrações normalizam valores legados fora da faixa antes de criar as constraints;
- testes existentes ampliados para validar as novas constraints e traduções;
- script Windows/Linux local separado da validação de higiene do pacote;
- documentação de execução e migrações atualizada.

## v5.0.0 — 04/08/2026

### Fluxo de tarefas

- autorização centralizada em `tasks/permissions.py`;
- máquina de estados centralizada em `tasks/services.py`;
- conclusão e avaliações transacionais;
- exclusão de tarefa bloqueada após qualquer histórico e serializada com comentários/execução;
- aprovação final congela avaliações;
- proprietário incluído na fila de revisão;
- autoatribuições excluídas das pendências de stakeholder;
- superusuário Django reconhecido como administrador da aplicação.

### Auditoria e banco

- `TaskRate.updated_at`;
- `TaskReview.cycle_number`;
- `TaskReview.evaluation_snapshot`, incluindo contexto da tarefa e da atribuição;
- revisão imutável;
- novas constraints e normalização de dados legados;
- Admin somente leitura para avaliações e revisões.

### Segurança e privacidade

- ações mutáveis somente por `POST`;
- anexos privados;
- solicitação pública sem vazamento de status;
- nomes ocultos em links públicos por padrão;
- checklist pré-tarefa restrito ao estado correto.

### Testes e documentação

- 26 testes de tarefas;
- 17 testes das funcionalidades integradas;
- validadores estáticos e de links;
- scripts de validação para Windows/Linux;
- documentação funcional e técnica revisada.

## v4 — histórico

A v4 introduziu a primeira camada de proteção do fluxo, constraints de tarefas e avaliações e testes iniciais. A v5 amplia o contrato com congelamento pós-aprovação, auditoria por ciclos, privacidade dos links públicos, superusuários e documentação consolidada.
