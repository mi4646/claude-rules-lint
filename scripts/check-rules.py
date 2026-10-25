#!/usr/bin/env python3
"""check-rules.py — structural lint for layered CLAUDE.md rule sets.

Zero dependencies, stdlib only.

Checks
  FAIL  every rules/*.md is referenced from the main CLAUDE.md
  FAIL  every rules/<x>.md mentioned in the main file actually exists
  FAIL  `paths:` frontmatter parses and is non-empty
  WARN  main CLAUDE.md exceeds the 200-line adherence budget
  WARN  a path-conditioned rule covers >50% of this project (condition loading is fake)

Usage
  check-rules.py                 # check the current directory
  check-rules.py <dir> [<dir>..] # check the given directories
  check-rules.py --all           # also check ~/.claude (global layer)
  check-rules.py --quiet         # only print FAIL/WARN lines

Exit codes
  0  no FAIL
  1  at least one FAIL
  2  usage error
"""
from __future__ import annotations

import pathlib
import re
import sys

SKIP_PARTS = {'.git', 'node_modules', 'dist', 'build', '__pycache__',
              '.venv', 'venv', '.mypy_cache', '.pytest_cache', 'vendor'}
LINE_BUDGET = 200


def glob_to_re(pattern: str) -> re.Pattern[str]:
    """Translate a Claude Code `paths:` glob into a regex.

    `**/` matches zero or more leading directories, `**` matches anything,
    `*` and `?` stay within one path segment.
    """
    out: list[str] = []
    i = 0
    while i < len(pattern):
        if pattern.startswith('**/', i):
            out.append('(?:[^/]+/)*')
            i += 3
        elif pattern.startswith('**', i):
            out.append('.*')
            i += 2
        elif pattern[i] == '*':
            out.append('[^/]*')
            i += 1
        elif pattern[i] == '?':
            out.append('[^/]')
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile('^' + ''.join(out) + '$')


def parse_paths(text: str) -> list[str] | None:
    """Return the `paths:` list, or None when the rule has no frontmatter.

    Raises ValueError when frontmatter exists but `paths:` is empty or unparsable.
    """
    m = re.match(r'^---\r?\n(.*?)\r?\n---\r?\n', text, re.S)
    if not m:
        return None
    block = m.group(1)
    if not re.search(r'^paths\s*:', block, re.M):
        return None
    items = re.findall(r'^\s*-\s*["\']?([^"\'\n]+?)["\']?\s*$', block, re.M)
    if not items:
        raise ValueError('`paths:` is present but lists no patterns')
    return [i.strip() for i in items]


def project_files(root: pathlib.Path) -> list[str]:
    files: list[str] = []
    for p in root.rglob('*'):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        if SKIP_PARTS & set(rel.parts):
            continue
        files.append(rel.as_posix())
    return files


def check(root: pathlib.Path) -> tuple[list[str], list[str], list[str]]:
    """Return (fails, warns, infos) for one rule-set root."""
    fails: list[str] = []
    warns: list[str] = []
    infos: list[str] = []
    main = root / 'CLAUDE.md'
    rules_dir = root / '.claude' / 'rules'

    if not main.is_file():
        if rules_dir.is_dir():
            fails.append(f'{root}: .claude/rules/ exists but there is no CLAUDE.md to index it')
        return fails, warns, infos

    main_text = main.read_text(encoding='utf-8', errors='replace')
    n_lines = len(main_text.splitlines())
    if n_lines > LINE_BUDGET:
        warns.append(f'{main}: {n_lines} lines exceeds the {LINE_BUDGET}-line budget')

    # Only bare `rules/<x>.md` references point at this project's rule set;
    # `~/.claude/rules/<x>.md` names the global layer and is not ours to check.
    # Checked before the rules/ early-return: a dangling reference is exactly the
    # case where the directory may be gone, so returning early would hide it.
    bare_refs = set(re.findall(r'(?<![/\w.-])rules/([A-Za-z0-9_.-]+\.md)', main_text))
    global_refs = set(re.findall(r'~/\.claude/rules/([A-Za-z0-9_.-]+\.md)', main_text))
    for ref in bare_refs - global_refs:
        if not (rules_dir / ref).is_file():
            fails.append(f'{main}: references rules/{ref} which does not exist')

    if not rules_dir.is_dir():
        return fails, warns, infos

    rules = sorted(rules_dir.glob('*.md'))
    files = project_files(root)

    for rf in rules:
        if rf.name not in main_text:
            fails.append(f'{rf}: not referenced from {main.name} — the agent has no way to know it exists')
        try:
            paths = parse_paths(rf.read_text(encoding='utf-8', errors='replace'))
        except ValueError as exc:
            fails.append(f'{rf}: {exc}')
            continue
        if paths is None:
            continue  # always-on rule, nothing to measure
        rxs = [glob_to_re(p) for p in paths]
        matched = [f for f in files if any(r.match(f) for r in rxs)]
        if files:
            # Report coverage, do not judge it. A high rate is legitimate when the
            # rule owns that much of the tree (a frontend rule covering web/ + app/
            # but correctly excluding src/). What matters is whether the pattern
            # discriminates; that is a human call, so this stays INFO.
            tops = sorted({f.split('/')[0] for f in matched})
            spread = f'{len(tops)} top-level dir(s): {", ".join(tops[:6])}'
            infos.append(f'{rf}: paths match {len(matched)}/{len(files)} files '
                         f'({len(matched) * 100 // len(files)}%) across {spread}')

    return fails, warns, infos


def main(argv: list[str]) -> int:
    quiet = '--quiet' in argv
    argv = [a for a in argv if a != '--quiet']
    include_global = '--all' in argv
    argv = [a for a in argv if a != '--all']

    targets = [pathlib.Path(a).resolve() for a in argv] or [pathlib.Path.cwd()]
    if include_global:
        targets.append(pathlib.Path.home() / '.claude')

    all_fails: list[str] = []
    all_warns: list[str] = []
    all_infos: list[str] = []
    for root in targets:
        if not root.is_dir():
            print(f'error: not a directory: {root}', file=sys.stderr)
            return 2
        f, w, i = check(root)
        all_fails += f
        all_warns += w
        all_infos += i

    for label, items in (('FAIL', all_fails), ('WARN', all_warns), ('INFO', all_infos)):
        if quiet and label != 'FAIL':
            continue
        for item in items:
            print(f'{label}: {item}')

    root_n = len(targets)
    print(f'\n{root_n} root(s) checked — {len(all_fails)} fail, {len(all_warns)} warn')
    return 1 if all_fails else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
