# Correções realizadas — ERGO v5

A versão v5 corrige as falhas encontradas na auditoria do fluxo original e integra as extensões ao mesmo contrato de segurança.

## Falhas corrigidas

1. edição de tarefa alheia;
2. inclusão e remoção de papéis sem autorização;
3. operações destrutivas por `GET`;
4. mudança do status de outro executor;
5. gravação direta de `DONE` sem autoavaliação;
6. conclusão da atribuição de outra pessoa;
7. notas inválidas e erros 500 por valores não numéricos;
8. avaliação por usuário sem papel/permissão;
9. autoavaliação disfarçada de avaliação de stakeholder;
10. remoção da avaliação de outra pessoa;
11. atribuições e avaliações duplicadas;
12. fila de avaliação confundindo autoavaliação com avaliação do usuário atual;
13. proprietário fora da própria fila de revisão;
14. autoatribuição exibida como pendente para o próprio executor;
15. avaliações mutáveis após aprovação final;
16. revisões históricas sem identificação de ciclo ou snapshot;
17. checklist pré-tarefa respondido após conclusão;
18. superusuário Django não reconhecido sem alteração manual de `role`;
19. status de solicitação pública inferível por e-mail;
20. exposição padrão dos nomes da equipe em links públicos;
21. alteração de registros de auditoria pelo Django Admin;
22. exclusão de tarefa com histórico de execução/auditoria;
23. snapshot de revisão sem contexto da tarefa e da atribuição;
24. corrida entre exclusão de tarefa e criação de comentários/alteração de atribuições.

Detalhes técnicos estão em [`ALTERACOES_V5.md`](ALTERACOES_V5.md) e [`docs/FLUXO_DE_TAREFAS_VALIDADO.md`](docs/FLUXO_DE_TAREFAS_VALIDADO.md).


## Ajustes complementares v5.1

- tradução de estados e rótulos PT-BR pendentes;
- constraint de banco para dificuldade de tarefas e modelos no intervalo de 0 a 5;
- migrações com normalização segura de dados legados;
- separação entre validação local e higiene do pacote de distribuição.
