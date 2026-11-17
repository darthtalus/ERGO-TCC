# Guia funcional — ERGO v5

## 1. Proprietário da tarefa

1. abra **Nova tarefa**;
2. informe nome, descrição, estimativa e dificuldade;
3. adicione executor(es) e stakeholder(s);
4. acompanhe cada atribuição separadamente;
5. use histórico e colaboração para revisar entregas;
6. devolva para ajustes ou aprove somente após conclusão válida.

O proprietário não pode avaliar/revisar a própria atribuição quando também é executor.

## 2. Executor

1. veja suas atribuições na página inicial ou Kanban;
2. preencha o checklist preventivo enquanto estiver em `DOING`/`PAUSED`;
3. pause, retome ou cancele apenas sua própria atribuição;
4. conclua informando quatro notas inteiras de 1 a 5;
5. se houver devolução, a atribuição volta a `DOING`;
6. corrija e conclua novamente.

Uma tentativa inválida não deve mudar o estado.

## 3. Stakeholder

1. abra **Tarefas como stakeholder** ou o histórico;
2. avalie apenas executores concluídos;
3. informe Efetividade de 1 a 5;
4. registre uma revisão pendente, devolvida ou aprovada;
5. não avalie sua própria atribuição.

Após aprovação final, avaliações e revisões daquele executor ficam congeladas.

## 4. Administrador

- gerencia tarefas e papéis no alcance organizacional;
- acessa dashboard organizacional;
- pode revisar outros executores;
- não pode burlar separação de funções;
- não deve usar o Django Admin para alterar estados/avaliações históricas.

`createsuperuser` já é reconhecido como privilegiado sem editar o campo customizado `role`.

## 5. Colaboração

Na tela de colaboração:

- registre comentários;
- envie anexos permitidos de até 10 MB;
- marque checklist operacional;
- consulte checklists preventivos;
- registre decisões de revisão.

O download do anexo revalida acesso à tarefa.

## 6. Modelos e recorrência

- crie um modelo com checklist textual;
- gere uma tarefa e confirme que os itens foram copiados;
- configure recorrência diária, semanal ou mensal;
- execute o gerador manualmente ou por agendamento.

## 7. Links públicos

O proprietário gera/revoga o link. Por padrão, a página exibe contagens, não nomes. Uma pessoa externa pode solicitar participação, mas não consultar o status apenas informando o e-mail.

## 8. Sensores

- cadastro manual pela tela;
- geração/revogação de chave;
- POST externo com `X-ERGO-API-Key` ou Bearer;
- valide unidades e calibração antes de interpretar resultados.

## 9. Relatórios

- PDF: síntese exploratória;
- CSV pseudonimizado: reduz identificadores diretos, mas não garante anonimato irreversível;
- APIs de leitura: respeitam o escopo do usuário.
