# Documentação técnica resumida — ERGO v5

## Finalidade

O ERGO registra tarefas, papéis, avaliações e efetividade, relacionando dimensões Ambiente/Acesso, Cognição e Comportamento. A versão v5 adiciona um fluxo protegido e auditável, sem transformar as heurísticas do painel em diagnóstico científico.

## Papéis

- proprietário: administra a tarefa e pode revisar outros executores;
- executor: controla seu próprio estado e conclui com autoavaliação;
- stakeholder: acompanha e avalia outros executores;
- administrador/superusuário: alcance organizacional, sem permissão para autoavaliar como stakeholder;
- externo: apenas link público e solicitação de participação.

## Estado por atribuição

```text
DOING <-> PAUSED
DOING/PAUSED -> CANCELED -> DOING
DOING/PAUSED --conclusão válida--> DONE
DONE --RETURNED--> DOING
DONE --APPROVED--> FINAL
```

`DONE` não é uma opção genérica. A conclusão grava a autoavaliação e o estado na mesma transação.

## Avaliações e revisões

- autoavaliação: quatro notas de 1–5;
- avaliação de stakeholder: Efetividade de 1–5;
- revisão: pendente, devolvida ou aprovada;
- cada revisão registra ciclo e snapshot;
- aprovação congela o ciclo final.

## Segurança

- autorização no servidor;
- ações de escrita em `POST`;
- CSRF nas interfaces de sessão;
- chave dedicada para POST de sensores;
- anexos privados;
- Admin sem atalhos para reescrever auditoria;
- nomes em links públicos ocultos por padrão.

## Análises

A área **Análises e fluxo de trabalho** oferece dashboard, gráficos, recomendações, Kanban, colaboração, modelos, recorrência, sensores, PDF e CSV pseudonimizado.

## Internacionalização

Interface em `pt-br` e `en-us`. Strings de backend e frontend usam o sistema de tradução do Django. Após alterar mensagens:

```bash
python manage.py makemessages -l pt_BR -l en
python manage.py compilemessages
```

## Testes

```powershell
.\scripts\run_validation_windows.ps1
```

A versão contém 43 testes isolados e validadores estáticos. Evidências e limitações: [`RELATORIO_VALIDACAO_V5.md`](RELATORIO_VALIDACAO_V5.md).

## Referências internas

- [`FLUXO_DE_TAREFAS_VALIDADO.md`](FLUXO_DE_TAREFAS_VALIDADO.md)
- [`ROTAS_E_PERMISSOES.md`](ROTAS_E_PERMISSOES.md)
- [`ARQUITETURA_E_MODELO_DE_DADOS.md`](ARQUITETURA_E_MODELO_DE_DADOS.md)
- [`API_E_INTEGRACOES.md`](API_E_INTEGRACOES.md)
- [`SEGURANCA_PRIVACIDADE_E_LGPD.md`](SEGURANCA_PRIVACIDADE_E_LGPD.md)


## Ajustes v5.1

- traduções PT-BR pendentes foram completadas;
- tarefas e modelos de tarefa receberam constraints de dificuldade entre 0 e 5;
- a validação local foi separada da higiene de uma cópia limpa para distribuição.
