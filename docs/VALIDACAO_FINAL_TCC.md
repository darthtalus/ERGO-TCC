# Validação final — 17/11/2026

Esta revisão consolida as três correções aplicadas à versão 5.1 durante a validação do projeto. Os relatórios anteriores em `docs/` preservam o histórico daquela versão (43 testes); a suíte atual contém 48 testes (30 em `tasks` e 18 em `upgrades`).

## Resultado dos testes automatizados

Comando executado no ambiente Windows local:

```powershell
python manage.py test tasks upgrades --settings=ergo.test_settings -v 2
```

Resultado observado: `Ran 48 tests in 2.069s` / `OK`. O banco de testes é SQLite em memória.

## Verificações manuais realizadas

- Atribuições independentes por executor e controle de acesso por papel.
- Checklist ergonômico individual, comentários e anexos protegidos.
- Autoavaliação, avaliação do interessado, devolução para ajustes, novo ciclo e aprovação final.
- Histórico por ciclo, com cópia das avaliações e registro temporal.
- Modelos de tarefa, cópia do checklist e geração recorrente idempotente no cenário mensal testado.
- Listagem do criador sem duplicidade, indicação de ausência de executor e bloqueio visual após aprovação.
- Acesso indevido às rotas internas e ao download de anexos retornando HTTP 403.

As verificações descrevem os cenários de aceite executados e não constituem certificação de segurança, validação científica do instrumento ou teste de carga.

## Distribuição do código

Este pacote contém o código-fonte consolidado, documentação, migrações, arquivos estáticos de origem e configuração de exemplo. Não contém o banco da demonstração, credenciais, anexos nem ambiente virtual. Recomenda-se manter o repositório privado até obter autorização formal para divulgação, preservando a autoria e os créditos do projeto original.
