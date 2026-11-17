"""Static validation for the integrated ERGO analytics/workflow features.

No Django installation is required. Runtime behavior is covered by the Django
suite documented in ``docs/TESTES_E_VALIDACAO.md``.
"""
from __future__ import annotations

import compileall
import gettext
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def validate_python() -> list[str]:
    ok = compileall.compile_dir(
        ROOT,
        quiet=1,
        rx=re.compile(r'(^|/)(venv|\.venv|media|private_media|test_media|test_private_media|__pycache__)(/|$)'),
    )
    return [] if ok else ['Python compilation failed.']


def validate_templates() -> list[str]:
    errors: list[str] = []
    pairs = {
        'if': 'endif', 'for': 'endfor', 'block': 'endblock', 'with': 'endwith',
        'autoescape': 'endautoescape', 'comment': 'endcomment', 'filter': 'endfilter',
        'spaceless': 'endspaceless', 'blocktrans': 'endblocktrans',
    }
    for path in (ROOT / 'templates').rglob('*.html'):
        stack: list[str] = []
        text = path.read_text(encoding='utf-8', errors='ignore')
        for match in re.finditer(r'{%\s*([^%]+?)\s*%}', text):
            token = match.group(1).strip().split()[0]
            if token in pairs:
                stack.append(token)
            elif token.startswith('end'):
                if not stack or pairs[stack[-1]] != token:
                    errors.append(f'{path}: mismatched {token}')
                    break
                stack.pop()
        if stack:
            errors.append(f'{path}: unclosed template tags {stack}')
    return errors


def validate_translations() -> list[str]:
    ids: set[str] = set()
    files = (
        list((ROOT / 'upgrades').rglob('*.py'))
        + list((ROOT / 'tasks').rglob('*.py'))
        + list((ROOT / 'templates' / 'upgrades').rglob('*.html'))
        + [ROOT / 'templates/tasks/task_public.html']
    )
    patterns = [
        r"_\(\s*'([^']+)'\s*\)", r'_\(\s*"([^"]+)"\s*\)',
        r'{%\s*trans\s+"([^"]+)"\s*%}', r"{%\s*trans\s+'([^']+)'\s*%}",
    ]
    for path in files:
        text = path.read_text(encoding='utf-8')
        for pattern in patterns:
            ids.update(re.findall(pattern, text))
    with (ROOT / 'locale/pt_BR/LC_MESSAGES/django.mo').open('rb') as handle:
        translations = gettext.GNUTranslations(handle)
    catalog = getattr(translations, '_catalog', {})
    # Existing legacy screens contain untranslated strings. This validator
    # focuses on workflow/public-share strings introduced or touched in v5.
    required = {
        'Task reviews are immutable audit records.',
        'This assignment is approved and its evaluations are final.',
        'A valid executor self-assessment is required before evaluation.',
        'Shared task', 'Request participation', 'Request sent',
        'Participant names are hidden on public links.',
        'Evaluation snapshot', 'Cycle',
        'This task cannot be deleted because it already has workflow history.',
        'Pending', 'Rejected',
    }
    missing = sorted(msgid for msgid in required if not catalog.get(msgid))
    return [f'Missing PT-BR translation: {msgid}' for msgid in missing]


def validate_regressions() -> list[str]:
    errors: list[str] = []
    targets = [ROOT / 'upgrades', ROOT / 'templates' / 'upgrades']
    forbidden = {
        'payload.get-zero-loss': re.compile(r'payload\.get\([^\n]+\)\s+or\s+None'),
        'old-pending-review-query': re.compile(r'exclude\(upgrade_reviews__status'),
        'thirty-day-month': re.compile(r'timedelta\(days=30\)'),
        'public-attachment-url': re.compile(r'attachment\.url'),
    }
    for path in [p for target in targets for p in target.rglob('*') if p.is_file() and p.suffix in {'.py', '.html'}]:
        text = path.read_text(encoding='utf-8', errors='ignore')
        for name, pattern in forbidden.items():
            if pattern.search(text):
                errors.append(f'{path}: forbidden regression pattern {name}')

    task_views = (ROOT / 'tasks/views.py').read_text(encoding='utf-8')
    if "request.GET.get('email'" in task_views:
        errors.append('tasks/views.py: public join-request status leak regression')
    if "request.user.role in ['ADMIN', 'SUPERADMIN']" in task_views:
        errors.append('tasks/views.py: duplicated privilege rule bypasses superuser support')

    required = [
        ROOT / 'tasks/migrations/0017_task_difficulty_range.py',
        ROOT / 'tasks/migrations/0018_task_workflow_integrity.py',
        ROOT / 'tasks/migrations/0019_taskrate_updated_at.py',
        ROOT / 'tasks/migrations/0020_task_difficulty_constraint.py',
        ROOT / 'tasks/permissions.py',
        ROOT / 'tasks/services.py',
        ROOT / 'tasks/tests.py',
        ROOT / 'upgrades/migrations/0002_security_workflow_and_validation.py',
        ROOT / 'upgrades/migrations/0003_task_review_audit_snapshot.py',
        ROOT / 'upgrades/migrations/0004_task_template_difficulty_constraint.py',
        ROOT / 'upgrades/tests.py',
        ROOT / 'ergo/test_settings.py',
        ROOT / 'scripts/validate_task_workflow.py',
        ROOT / 'scripts/validate_documentation_links.py',
    ]
    errors.extend(f'Missing required file: {path}' for path in required if not path.exists())
    return errors


def validate_package_config() -> list[str]:
    errors: list[str] = []
    requirements = (ROOT / 'requirements.txt').read_text(encoding='utf-8')
    if 'Django>=5.2.16,<5.3' not in requirements:
        errors.append('requirements.txt must pin the validated Django 5.2 maintenance line')
    if 'sqlparse>=0.5.4' not in requirements:
        errors.append('requirements.txt must require the corrected sqlparse line')
    settings = (ROOT / 'ergo/settings.py').read_text(encoding='utf-8')
    if 'PUBLIC_SHARE_SHOW_PARTICIPANT_NAMES' not in settings:
        errors.append('Missing public-share participant privacy setting')
    if "'staticfiles': {" not in settings or 'CompressedStaticFilesStorage' not in settings:
        errors.append('Django 5.2 STORAGES configuration is missing for static files')
    if 'DATABASE_URL is not configured' not in settings:
        errors.append('Missing explicit DATABASE_URL configuration error')
    if "os.environ.get('PRIVATE_MEDIA_ROOT')" not in settings:
        errors.append('PRIVATE_MEDIA_ROOT must be configurable by environment')
    return errors


def main() -> int:
    errors = (
        validate_python()
        + validate_templates()
        + validate_translations()
        + validate_regressions()
        + validate_package_config()
    )
    if errors:
        print('\n'.join(f'ERROR: {error}' for error in errors))
        return 1
    print(
        'Static validation passed: Python, templates, required PT-BR strings, '
        'migrations, privacy configuration and regression patterns.'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
