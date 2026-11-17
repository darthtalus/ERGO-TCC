"""Validate relative Markdown links in the ERGO documentation tree."""
from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
MARKDOWN_FILES = list(ROOT.glob('*.md')) + list((ROOT / 'docs').rglob('*.md'))
LINK_RE = re.compile(r'(?<!!)\[[^\]]*\]\(([^)]+)\)')


def main() -> int:
    errors: list[str] = []
    for document in MARKDOWN_FILES:
        text = document.read_text(encoding='utf-8', errors='strict')
        for raw_target in LINK_RE.findall(text):
            target = raw_target.strip().split()[0].strip('<>')
            if not target or target.startswith(('#', 'http://', 'https://', 'mailto:', 'tel:')):
                continue
            path_part = unquote(target.split('#', 1)[0])
            if not path_part:
                continue
            resolved = (document.parent / path_part).resolve()
            try:
                resolved.relative_to(ROOT.resolve())
            except ValueError:
                errors.append(f'{document.relative_to(ROOT)}: link escapes project root: {target}')
                continue
            if not resolved.exists():
                errors.append(f'{document.relative_to(ROOT)}: missing target: {target}')
    if errors:
        for error in errors:
            print(f'ERROR: {error}')
        return 1
    print(f'Documentation links passed ({len(MARKDOWN_FILES)} Markdown files checked).')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
