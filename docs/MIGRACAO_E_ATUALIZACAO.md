# Migração e atualização para ERGO v5

## 1. Antes de atualizar

1. pare aplicação e geradores de recorrência;
2. faça backup consistente do banco;
3. copie `private_media/` e valide a restauração;
4. registre a versão atual e o resultado de `showmigrations`;
5. extraia a v5 em pasta nova;
6. não copie `venv`, `.pyc`, cache, banco local ou arquivos temporários.

## 2. Configuração

Crie `.env` a partir de `.env.example`. Preserve uma `SECRET_KEY` estável em produção. Revise especialmente:

- `DATABASE_URL`;
- `DEBUG`;
- `ALLOWED_HOSTS`;
- `CSRF_TRUSTED_ORIGINS`;
- `PRIVATE_MEDIA_ROOT`;
- `PUBLIC_SHARE_SHOW_PARTICIPANT_NAMES`.

## 3. Instalação e plano

```powershell
py -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python manage.py showmigrations tasks upgrades
python manage.py migrate --plan
```

## 4. Migrações do fluxo

### `tasks.0018_task_workflow_integrity`

Normaliza dados legados antes de ativar constraints:

- tipos e estados inválidos;
- stakeholder com estado diferente de `NONE`;
- notas fora de 1–5;
- autores/payloads inconsistentes;
- `DONE` sem autoavaliação;
- atribuições e avaliações duplicadas.

Depois cria constraints de unicidade, faixa e consistência.

### `tasks.0019_taskrate_updated_at`

Adiciona `updated_at` às avaliações e preenche registros antigos com `created_at`. Esse campo permite identificar a versão mais recente de uma avaliação no ciclo.

### `upgrades.0002_security_workflow_and_validation`

Adiciona:

- armazenamento privado e validação de anexos;
- `anchor_day` da recorrência mensal;
- checklist operacional;
- ocorrências idempotentes;
- chave de API de sensores;
- validadores de faixas ambientais.

A migração tenta mover anexos legados de `MEDIA_ROOT` para `PRIVATE_MEDIA_ROOT`. Confirme a cópia antes de remover o backup.

### `upgrades.0003_task_review_audit_snapshot`

Adiciona:

- `cycle_number`;
- `evaluation_snapshot`;
- constraints de status e ciclo;
- ordenação determinística das revisões.

Revisões antigas recebem ciclos por melhor esforço. Valores históricos que não podem ser reconstruídos não são inventados; o snapshot pode permanecer vazio.

## 5. Aplicação

```powershell
python manage.py migrate
python manage.py check
python manage.py makemigrations --check --dry-run
```

## 6. Validação obrigatória

```powershell
.\scripts\run_validation_windows.ps1
```

Esse comando executa validadores estáticos, checagem do Django, verificação de migrações e os 43 testes isolados.

## 7. Smoke test pós-migração

Use contas separadas para proprietário, executor e stakeholder:

1. criar tarefa;
2. atribuir papéis;
3. pausar e retomar;
4. concluir com autoavaliação;
5. avaliar e devolver;
6. concluir novamente e aprovar;
7. confirmar bloqueio após aprovação;
8. testar histórico, Kanban, colaboração e anexos;
9. abrir link público e confirmar privacidade.

## 8. Rollback

Migrações que alteram ou normalizam dados não devem ser revertidas cegamente. Para rollback seguro:

1. pare a aplicação;
2. restaure banco e arquivos privados do mesmo ponto no tempo;
3. restaure a versão anterior do código;
4. execute testes e smoke test;
5. documente a causa.

## 9. Banco limpo

Este pacote não contém dump preenchido. Para uma instalação nova, crie um banco vazio, rode `migrate` e crie um superusuário. Não importe dumps antigos sem avaliar dados pessoais, constraints e compatibilidade.


## Ajustes v5.1

- traduções PT-BR pendentes foram completadas;
- tarefas e modelos de tarefa receberam constraints de dificuldade entre 0 e 5;
- a validação local foi separada da higiene de uma cópia limpa para distribuição.
