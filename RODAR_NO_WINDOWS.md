# Como instalar e rodar o ERGO v5 no Windows

Este guia parte de uma pasta nova e de um MySQL já instalado. O pacote não contém `.env`, banco preenchido ou ambiente virtual.

## 1. Extrair o ZIP

Extraia em uma pasta nova, por exemplo:

```text
C:\Users\SEU_USUARIO\Documents\Python Projects\ERGO-v5\ergo-main
```

Abra essa pasta no VS Code. No terminal integrado, confirme:

```powershell
dir
```

Devem existir `manage.py`, `requirements.txt`, `tasks`, `upgrades`, `docs` e `templates`.

## 2. Criar e ativar o ambiente virtual

```powershell
py -m venv venv
.\venv\Scripts\Activate.ps1
```

Se o PowerShell bloquear scripts:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
```

O prompt deve começar com `(venv)`.

## 3. Instalar as dependências

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 4. Criar o `.env`

Copie o exemplo:

```powershell
Copy-Item .env.example .env
```

Edite `.env` e ajuste pelo menos:

```text
SECRET_KEY=troque-por-uma-chave-longa
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=mysql://ergo:ergo123@127.0.0.1:3306/ergo
PUBLIC_SHARE_SHOW_PARTICIPANT_NAMES=False
```

Para desenvolvimento local, gere uma chave com:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

## 5. Confirmar o serviço MySQL

No computador usado nesta instalação, o serviço foi identificado como `MySQL97`:

```powershell
Get-Service MySQL97
```

Se estiver parado, abra PowerShell como administrador:

```powershell
Start-Service MySQL97
```

O executável foi encontrado em:

```text
C:\Program Files\MySQL\MySQL Server 9.7\bin\mysql.exe
```

Em outro computador, descubra o caminho com:

```powershell
Get-CimInstance Win32_Service | Where-Object {$_.Name -like "MySQL*"} | Select-Object Name, State, PathName
```

## 6. Criar banco e usuário

Entre como root:

```powershell
& "C:\Program Files\MySQL\MySQL Server 9.7\bin\mysql.exe" -u root -p
```

No console MySQL:

```sql
CREATE DATABASE IF NOT EXISTS ergo
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_general_ci;

CREATE USER IF NOT EXISTS 'ergo'@'localhost' IDENTIFIED BY 'ergo123';
CREATE USER IF NOT EXISTS 'ergo'@'127.0.0.1' IDENTIFIED BY 'ergo123';
ALTER USER 'ergo'@'localhost' IDENTIFIED BY 'ergo123';
ALTER USER 'ergo'@'127.0.0.1' IDENTIFIED BY 'ergo123';
GRANT ALL PRIVILEGES ON ergo.* TO 'ergo'@'localhost';
GRANT ALL PRIVILEGES ON ergo.* TO 'ergo'@'127.0.0.1';
FLUSH PRIVILEGES;
EXIT;
```

Use uma senha diferente em ambiente real e atualize a `DATABASE_URL`.

## 7. Aplicar as migrações

Faça backup antes de atualizar um banco existente. Depois:

```powershell
python manage.py migrate
```

Migrações importantes:

```text
tasks.0018_task_workflow_integrity
tasks.0019_taskrate_updated_at
upgrades.0002_security_workflow_and_validation
upgrades.0003_task_review_audit_snapshot
tasks.0020_task_difficulty_constraint
upgrades.0004_task_template_difficulty_constraint
```

## 8. Criar administrador

```powershell
python manage.py createsuperuser
```

Na v5, `is_superuser=True` já concede os privilégios da aplicação; não é necessário editar manualmente o campo `role`.

## 9. Validar antes de iniciar

```powershell
.\scripts\run_validation_windows.ps1
```

O script executa:

```text
validador do contrato do fluxo
validador estático geral
validador dos links da documentação
manage.py check
verificação de migrações pendentes
43 testes automatizados em SQLite temporário
```

A suíte de testes não usa o banco MySQL do `.env`. O script acima é próprio para uma instalação local e aceita a presença de `venv`, `.env` e backups.

Para validar uma cópia limpa destinada à distribuição, antes de criar esses arquivos, use:

```powershell
.\scripts\run_package_validation_windows.ps1
```

## 10. Rodar o servidor

```powershell
python manage.py runserver
```

Acesse:

```text
http://127.0.0.1:8000/
http://127.0.0.1:8000/tasks/
http://127.0.0.1:8000/upgrades/
```

## Erros comuns

### `Activate.ps1` não existe

Crie o ambiente antes:

```powershell
py -m venv venv
```

### `No DATABASE_URL environment variable set`

Confirme que `.env` está na mesma pasta de `manage.py`:

```powershell
Get-Content .env
```

### `Can't connect to MySQL server on 127.0.0.1`

```powershell
Get-Service MySQL97
Start-Service MySQL97
```

### `Access denied for user 'ergo'@'localhost'`

Entre como root e reaplique `ALTER USER` e `GRANT` do passo 6.

### `mysql` não é reconhecido

Use o caminho completo:

```powershell
& "C:\Program Files\MySQL\MySQL Server 9.7\bin\mysql.exe" -u root -p
```

### Porta 8000 ocupada

```powershell
python manage.py runserver 8001
```

### Esqueci a senha root

Use o procedimento oficial de redefinição da sua versão do MySQL. Não deixe arquivo de inicialização contendo senha no disco depois do processo e reinicie o serviço normal antes de voltar ao Django.

## Atualização diária

Para rodar em outro dia:

```powershell
cd "C:\caminho\para\ERGO-v5\ergo-main"
.\venv\Scripts\Activate.ps1
Get-Service MySQL97
python manage.py runserver
```
