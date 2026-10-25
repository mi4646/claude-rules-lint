#!/usr/bin/env python3
"""Tests for check-rules.py and the PostToolUse hook.

Standard library only, so CI needs no install step.

Run:  python3 -m unittest discover -s tests -v
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile
import textwrap
import unittest

REPO = pathlib.Path(__file__).resolve().parent.parent
CHECKER = REPO / 'scripts' / 'check-rules.py'
HOOK = REPO / 'hooks' / 'rules-lint-hook.py'

sys.path.insert(0, str(CHECKER.parent))
import importlib.util

_spec = importlib.util.spec_from_file_location('check_rules', CHECKER)
check_rules = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_rules)


def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CHECKER), *args],
        capture_output=True, text=True, timeout=60,
    )


def run_hook(payload: dict | str) -> subprocess.CompletedProcess[str]:
    body = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=body, capture_output=True, text=True, timeout=60,
    )


class Fixture:
    """A throwaway rule-set root on disk."""

    def __init__(self, main: str | None = None,
                 rules: dict[str, str] | None = None,
                 files: list[str] | None = None):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self._tmp.name)
        if main is not None:
            (self.root / 'CLAUDE.md').write_text(main, encoding='utf-8')
        for name, body in (rules or {}).items():
            d = self.root / '.claude' / 'rules'
            d.mkdir(parents=True, exist_ok=True)
            (d / name).write_text(body, encoding='utf-8')
        for rel in files or []:
            p = self.root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text('x', encoding='utf-8')

    def __enter__(self) -> pathlib.Path:
        return self.root

    def __exit__(self, *exc) -> None:
        self._tmp.cleanup()


def rule(paths: list[str] | None) -> str:
    """A rule file body, with or without `paths:` frontmatter."""
    if paths is None:
        return '# always on\n'
    body = '---\npaths:\n' + ''.join(f'  - "{p}"\n' for p in paths) + '---\n# conditional\n'
    return body


class GlobTranslation(unittest.TestCase):
    def test_double_star_slash_matches_zero_or_more_dirs(self):
        rx = check_rules.glob_to_re('**/*.py')
        self.assertTrue(rx.match('main.py'))
        self.assertTrue(rx.match('src/main.py'))
        self.assertTrue(rx.match('a/b/c/main.py'))
        self.assertFalse(rx.match('src/main.js'))

    def test_single_star_stays_within_a_segment(self):
        rx = check_rules.glob_to_re('src/*.py')
        self.assertTrue(rx.match('src/main.py'))
        self.assertFalse(rx.match('src/deep/main.py'))

    def test_trailing_glob_covers_subtree(self):
        rx = check_rules.glob_to_re('web/src/**')
        self.assertTrue(rx.match('web/src/App.vue'))
        self.assertTrue(rx.match('web/src/a/b/c.ts'))
        self.assertFalse(rx.match('web/other/App.vue'))

    def test_question_mark_is_one_character(self):
        rx = check_rules.glob_to_re('v?.py')
        self.assertTrue(rx.match('v1.py'))
        self.assertFalse(rx.match('v12.py'))


class PathsParsing(unittest.TestCase):
    def test_no_frontmatter_is_always_on(self):
        self.assertIsNone(check_rules.parse_paths('# plain\n'))

    def test_frontmatter_without_paths_is_always_on(self):
        self.assertIsNone(check_rules.parse_paths('---\ntitle: x\n---\n# body\n'))

    def test_empty_paths_raises(self):
        with self.assertRaises(ValueError):
            check_rules.parse_paths('---\npaths:\n---\n# body\n')

    def test_parses_quoted_and_bare(self):
        body = '---\npaths:\n  - "src/**"\n  - tests/*.py\n---\n# x\n'
        self.assertEqual(check_rules.parse_paths(body), ['src/**', 'tests/*.py'])


class CleanSets(unittest.TestCase):
    def test_clean_set_passes(self):
        with Fixture(
            main='# T\n\n| rule | see |\n|---|---|\n| a | `rules/a.md` |\n',
            rules={'a.md': rule(['src/**'])},
            files=['src/main.py'],
        ) as root:
            proc = run([str(root)])
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertNotIn('FAIL', proc.stdout)

    def test_always_on_rule_without_paths_passes(self):
        with Fixture(main='# T\n`rules/a.md`\n', rules={'a.md': rule(None)}) as root:
            proc = run([str(root)])
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_project_without_rules_dir_passes(self):
        with Fixture(main='# T\n') as root:
            proc = run([str(root)])
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_global_reference_is_not_treated_as_a_project_rule(self):
        """`~/.claude/rules/x.md` names the global layer; it must not FAIL."""
        with Fixture(
            main='# T\n判据在 `~/.claude/rules/verification.md`\n',
            rules={'own.md': rule(None)},
        ) as root:
            (root / 'CLAUDE.md').write_text(
                '# T\n判据在 `~/.claude/rules/verification.md`\n见 `rules/own.md`\n',
                encoding='utf-8')
            proc = run([str(root)])
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertNotIn('verification.md', proc.stdout)


class Failures(unittest.TestCase):
    def test_unreferenced_rule_file_fails(self):
        with Fixture(main='# T\n', rules={'orphan.md': rule(None)}) as root:
            proc = run([str(root)])
        self.assertEqual(proc.returncode, 1)
        self.assertIn('orphan.md', proc.stdout)
        self.assertIn('not referenced', proc.stdout)

    def test_dangling_reference_fails(self):
        with Fixture(main='# T\n见 `rules/ghost.md`\n') as root:
            proc = run([str(root)])
        self.assertEqual(proc.returncode, 1)
        self.assertIn('ghost.md', proc.stdout)
        self.assertIn('does not exist', proc.stdout)

    def test_empty_paths_fails(self):
        with Fixture(main='# T\n`rules/a.md`\n', rules={'a.md': '---\npaths:\n---\n# x\n'}) as root:
            proc = run([str(root)])
        self.assertEqual(proc.returncode, 1)
        self.assertIn('lists no patterns', proc.stdout)

    def test_rules_without_main_file_fails(self):
        with Fixture(rules={'a.md': rule(None)}) as root:
            proc = run([str(root)])
        self.assertEqual(proc.returncode, 1)
        self.assertIn('no CLAUDE.md', proc.stdout)

    def test_all_failure_kinds_at_once(self):
        main = '# T\n见 `rules/ghost.md`\n\n' + '\n'.join(f'line {i}' for i in range(210))
        with Fixture(
            main=main + '\n见 `rules/real.md`\n',
            rules={'real.md': rule(['src/**']), 'orphan.md': rule(None),
                   'empty.md': '---\npaths:\n---\n# x\n'},
        ) as root:
            proc = run([str(root)])
        self.assertEqual(proc.returncode, 1)
        self.assertIn('ghost.md', proc.stdout)      # dangling reference
        self.assertIn('orphan.md', proc.stdout)     # unindexed
        self.assertIn('empty.md', proc.stdout)      # empty paths
        self.assertIn('exceeds the 200-line budget', proc.stdout)


class Warnings(unittest.TestCase):
    def test_long_main_file_warns_but_does_not_fail(self):
        main = '# T\n`rules/a.md`\n' + '\n'.join(f'line {i}' for i in range(210))
        with Fixture(main=main, rules={'a.md': rule(None)}) as root:
            proc = run([str(root)])
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn('WARN', proc.stdout)
        self.assertIn('200-line budget', proc.stdout)

    def test_coverage_is_reported_not_judged(self):
        """High coverage must never be a FAIL or a WARN — it needs human judgment."""
        files = [f'dir{i}/f.py' for i in range(20)]
        with Fixture(
            main='# T\n`rules/a.md`\n',
            rules={'a.md': rule(['**/*.py'])},
            files=files,
        ) as root:
            proc = run([str(root)])
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertNotIn('FAIL', proc.stdout)
        self.assertNotIn('WARN', proc.stdout)
        self.assertIn('INFO', proc.stdout)
        # 20 of the 22 files present (the fixture's own CLAUDE.md and rule file
        # are .md, not .py) — the exact figure is not the point, the level is.
        self.assertIn('paths match 20/22 files', proc.stdout)


class Cli(unittest.TestCase):
    def test_quiet_suppresses_info_and_warn(self):
        main = '# T\n`rules/a.md`\n' + '\n'.join(f'line {i}' for i in range(210))
        with Fixture(main=main, rules={'a.md': rule(['**/*.py'])},
                     files=['a.py']) as root:
            proc = run([str(root), '--quiet'])
        self.assertNotIn('INFO', proc.stdout)
        self.assertNotIn('WARN', proc.stdout)

    def test_multiple_roots(self):
        with Fixture(main='# T\n') as a, Fixture(main='# T\n') as b:
            proc = run([str(a), str(b)])
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn('2 root(s) checked', proc.stdout)

    def test_missing_directory_is_usage_error(self):
        proc = run(['/nonexistent/rules-lint-test'])
        self.assertEqual(proc.returncode, 2)


class Hook(unittest.TestCase):
    def test_non_rule_file_is_silent(self):
        with Fixture(main='# T\n') as root:
            proc = run_hook({'tool_name': 'Edit',
                             'tool_input': {'file_path': str(root / 'app/main.py')}})
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stderr.strip(), '')

    def test_clean_rule_set_is_silent(self):
        with Fixture(main='# T\n`rules/a.md`\n', rules={'a.md': rule(None)}) as root:
            proc = run_hook({'tool_name': 'Edit',
                             'tool_input': {'file_path': str(root / 'CLAUDE.md')}})
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stderr.strip(), '')

    def test_broken_rule_set_exits_2_with_stderr(self):
        """exit 2 is the only way a PostToolUse hook reaches Claude."""
        with Fixture(main='# T\n见 `rules/ghost.md`\n') as root:
            proc = run_hook({'tool_name': 'Edit',
                             'tool_input': {'file_path': str(root / 'CLAUDE.md')}})
        self.assertEqual(proc.returncode, 2)
        self.assertIn('rules-lint', proc.stderr)
        self.assertIn('ghost.md', proc.stderr)

    def test_editing_a_rule_file_also_triggers(self):
        with Fixture(main='# T\n见 `rules/ghost.md`\n', rules={'a.md': rule(None)}) as root:
            proc = run_hook({'tool_name': 'Write',
                             'tool_input': {'file_path': str(root / '.claude/rules/a.md')}})
        self.assertEqual(proc.returncode, 2)

    def test_non_editing_tool_is_silent(self):
        with Fixture(main='# T\n见 `rules/ghost.md`\n') as root:
            proc = run_hook({'tool_name': 'Read',
                             'tool_input': {'file_path': str(root / 'CLAUDE.md')}})
        self.assertEqual(proc.returncode, 0)

    def test_unparsable_input_is_silent(self):
        proc = run_hook('not json at all')
        self.assertEqual(proc.returncode, 0)

    def test_missing_file_path_is_silent(self):
        proc = run_hook({'tool_name': 'Edit', 'tool_input': {}})
        self.assertEqual(proc.returncode, 0)


class PluginManifest(unittest.TestCase):
    def test_manifests_are_valid_json(self):
        for rel in ('.claude-plugin/plugin.json',
                    '.claude-plugin/marketplace.json',
                    'hooks/hooks.json'):
            with self.subTest(rel=rel):
                json.loads((REPO / rel).read_text(encoding='utf-8'))

    def test_plugin_name_matches_marketplace_entry(self):
        plugin = json.loads((REPO / '.claude-plugin/plugin.json').read_text())
        market = json.loads((REPO / '.claude-plugin/marketplace.json').read_text())
        names = [p['name'] for p in market['plugins']]
        self.assertIn(plugin['name'], names)

    def test_hook_matcher_covers_the_editing_tools(self):
        hooks = json.loads((REPO / 'hooks/hooks.json').read_text())
        entries = hooks['hooks']['PostToolUse']
        matcher = '|'.join(e['matcher'] for e in entries)
        for tool in ('Write', 'Edit'):
            self.assertIn(tool, matcher)

    def test_version_is_a_semver(self):
        plugin = json.loads((REPO / '.claude-plugin/plugin.json').read_text())
        parts = plugin['version'].split('.')
        self.assertEqual(len(parts), 3)
        self.assertTrue(all(p.isdigit() for p in parts), plugin['version'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
