$ErrorActionPreference = "Stop"

Write-Host "[1/7] Contrato estático do fluxo"
python scripts/validate_task_workflow.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[2/7] Validação estática geral"
python scripts/validate_upgrades_static.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[3/7] Links da documentação"
python scripts/validate_documentation_links.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[4/7] Higiene do pacote limpo"
python scripts/validate_package_hygiene.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[5/7] Verificação do Django"
python manage.py check
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[6/7] Coerência das migrações"
python manage.py makemigrations --check --dry-run
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[7/7] Testes automatizados de tarefas e integrações"
python manage.py test tasks upgrades --settings=ergo.test_settings -v 2
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "VALIDAÇÃO DO PACOTE CONCLUÍDA COM SUCESSO" -ForegroundColor Green
