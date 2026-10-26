#!/usr/bin/env python3
"""PostToolUse hook: lint the rule set after a CLAUDE.md or .claude/rules/ edit.

Reads the hook payload on stdin, decides whether the edited path belongs to a
rule set, runs scripts/check-rules.py against the owning project, and reports.

Exit codes (Claude Code semantics):
  0  nothing to report — stay quiet
  2  findings — stderr is shown to Claude even though the tool already ran

Silence is deliberate: a hook that prints on every edit trains everyone to
ignore it.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
CHECKER = HERE.parent / 'scripts' / 'check-rules.py'

# Half-installed plugin: stay silent rather than crash on every edit. This must
# stay ahead of the module load below, which would otherwise raise ImportError.
if not CHECKER.is_file():
    sys.exit(0)

sys.path.insert(0, str(CHECKER.parent))
from importlib.util import module_from_spec, spec_from_file_location

_spec = spec_from_file_location('check_rules', CHECKER)
check_rules = module_from_spec(_spec)
_spec.loader.exec_module(check_rules)


def rule_root(path: pathlib.Path) -> pathlib.Path | None:
    """Return the project root this path belongs to, if it is part of a rule set.

    Delegates to check-rules.py so the hook and the CLI cannot disagree about
    what a root is. They once did: the hook stripped `.claude` unconditionally,
    so editing a user-level rule sent the checker to the home directory, which
    has no CLAUDE.md — a "no CLAUDE.md to index it" failure for a healthy set.
    """
    return check_rules.find_root(path)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0  # never fail a hook on unparsable input

    if payload.get('tool_name') not in ('Write', 'Edit', 'MultiEdit', 'NotebookEdit'):
        return 0

    raw = (payload.get('tool_input') or {}).get('file_path')
    if not raw:
        return 0

    path = pathlib.Path(raw).resolve()
    root = rule_root(path)
    if root is None:
        return 0

    try:
        proc = subprocess.run(
            [sys.executable, str(CHECKER), str(root), '--quiet'],
            capture_output=True, text=True, timeout=10,
        )
    except subprocess.TimeoutExpired:
        return 0  # a slow tree must not block editing

    findings = (proc.stdout + proc.stderr).strip()
    if proc.returncode == 0 or not findings:
        return 0

    sys.stderr.write(
        f'rules-lint: rule set at {root} has structural problems.\n'
        f'{findings}\n'
    )
    return 2


if __name__ == '__main__':
    sys.exit(main())
