#!/usr/bin/env bash
set -euo pipefail
python scripts/validate_task_workflow.py
python scripts/validate_upgrades_static.py
python scripts/validate_documentation_links.py
python scripts/validate_package_hygiene.py
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test tasks upgrades --settings=ergo.test_settings -v 2
echo "VALIDAÇÃO DO PACOTE CONCLUÍDA COM SUCESSO"
