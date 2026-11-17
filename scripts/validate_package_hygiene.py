"""Check the source tree for files that must never be shipped to users.

Python validators create ``__pycache__`` while running, so cache directories are
ignored here and removed by the packaging step. The final ZIP is scanned again.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_NAMES = {'.env', 'db.sqlite3'}
FORBIDDEN_SUFFIXES = {
    '.sql', '.sqlite', '.sqlite3', '.db', '.log',
    '.ttf', '.otf', '.woff', '.woff2', '.eot',
}
FORBIDDEN_DIRS = {'venv', '.venv', 'media', 'private_media', 'test_media', 'test_private_media'}


def main() -> int:
    errors: list[str] = []
    for path in ROOT.rglob('*'):
        rel = path.relative_to(ROOT)
        if '__pycache__' in rel.parts:
            continue
        if any(part in FORBIDDEN_DIRS for part in rel.parts):
            errors.append(f'forbidden directory/file: {rel}')
            continue
        if not path.is_file():
            continue
        if path.name in FORBIDDEN_NAMES or path.suffix.lower() in FORBIDDEN_SUFFIXES:
            errors.append(f'forbidden distributable file: {rel}')
    example = ROOT / '.env.example'
    if not example.exists():
        errors.append('missing .env.example')
    else:
        text = example.read_text(encoding='utf-8', errors='ignore')
        if 'SECRET_KEY=CHANGE_ME' not in text:
            errors.append('.env.example must use SECRET_KEY=CHANGE_ME')
        if 'DATABASE_URL=mysql://USER:PASSWORD@HOST:3306/DB_NAME' not in text:
            errors.append('.env.example must use database placeholders')
    if errors:
        for error in sorted(set(errors)):
            print(f'ERROR: {error}')
        return 1
    print('Package hygiene passed: no .env, databases, private media or font files in the source tree.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
