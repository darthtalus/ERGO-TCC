$ErrorActionPreference = "Stop"

Write-Host "[1/6] Contrato estático do fluxo"
python scripts/validate_task_workflow.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[2/6] Validação estática geral"
python scripts/validate_upgrades_static.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[3/6] Links da documentação"
python scripts/validate_documentation_links.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[4/6] Verificação do Django"
python manage.py check
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[5/6] Coerência das migrações"
python manage.py makemigrations --check --dry-run
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[6/6] Testes automatizados de tarefas e integrações"
python manage.py test tasks upgrades --settings=ergo.test_settings -v 2
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "VALIDAÇÃO LOCAL CONCLUÍDA COM SUCESSO" -ForegroundColor Green
