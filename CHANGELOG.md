# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Chinese README (`README.zh-CN.md`), with a language switcher at the top of both
  READMEs. Structure mirrors the English file section for section.

## [1.0.2] - 2026-10-26

### Fixed

- **The global layer was linted against the wrong rules directory.** `--all`
  appends `~/.claude` as a root, but `check()` hardcoded
  `root / '.claude' / 'rules'`, so it looked in `~/.claude/.claude/rules`, found
  nothing, and reported every `rules/x.md` reference as dangling — six false
  FAILs against a healthy user-level rule set. The same assumption in the hook
  (`rule_root()` stripping `.claude` unconditionally) sent the root to the home
  directory and produced a "`.claude/rules/` exists but there is no `CLAUDE.md`
  to index it" failure for a rule set whose `CLAUDE.md` was right there.
- Both now share one root resolver (`find_root()`), so the CLI and the hook
  cannot disagree about what a root is. Recognised layouts:
  `CLAUDE.md` + `rules/` (global layer, root == `~/.claude`) and
  `CLAUDE.md` + `.claude/rules/` (project).

### Added

- Six regression tests: nested/global layout passes, and it still catches a
  dangling reference, an unreferenced rule and a real hook finding. The suite
  stayed green through v1.0.1 because every fixture built the project layout
  only — the one layout the bug did not affect.

## [1.0.1] - 2026-10-25

### Added

- Test suite (`tests/test_rules_lint.py`): 33 standard-library `unittest` cases
  covering glob translation, `paths:` parsing, all four FAIL kinds, the
  warning/INFO split, CLI flags, every hook branch, and the plugin manifests.
  No install step.
- CI (`.github/workflows/ci.yml`): the suite on Python 3.9 and 3.13 (Linux),
  plus 3.13 on Windows for the hook's native-separator path handling; a
  self-check that the checker still passes a clean rule set *and* still fails
  a broken one; and a manifest gate tying the version in `plugin.json` to
  `marketplace.json`, the hook matcher, and a `## [version]` section in this file.

### Fixed

- **A dangling `rules/<x>.md` reference went unreported when the project had no
  `.claude/rules/` directory.** The reference check sat after an early return,
  so the exact case it exists to catch — the directory was deleted or renamed —
  was the case it silently skipped. Found by writing the test suite; three tests
  fail against the pre-fix code. Anyone on 1.0.0 is missing this check in
  exactly the situation it was written for.
- CI's Python 3.9 job failed before running a single test: `ubuntu-latest`
  moved to 26.04, which publishes no 3.9 build. 3.9 is the floor the README
  promises, so it is pinned to `ubuntu-22.04` rather than quietly raised.

## [1.0.0] - 2026-10-25

First release.

### Added

- `scripts/check-rules.py` — structural lint for a layered rule set. Standard
  library only, Python 3.9+, no dependencies.
  - **FAIL** — a rule file under `.claude/rules/` that no `CLAUDE.md` references.
    An unindexed rule is one the agent never learns exists.
  - **FAIL** — a `rules/<name>.md` reference in the main file that does not resolve.
  - **FAIL** — `paths:` frontmatter present but listing no patterns, so
    conditional loading can never fire.
  - **FAIL** — `.claude/rules/` exists with no `CLAUDE.md` to index it.
  - **WARN** — the main `CLAUDE.md` exceeds 200 lines, the point past which the
    official docs warn that adherence may drop.
  - **INFO** — per-rule `paths:` coverage and the top-level directories it reaches.
- PostToolUse hook (`hooks/hooks.json`) that lints the owning project after a
  `Write` / `Edit` / `MultiEdit` touches a `CLAUDE.md` or a `.claude/rules/*.md`,
  and surfaces findings to Claude via exit code 2. Every other edit resolves the
  path, exits 0, and produces no output.
- `skills/rules-lint/` — a skill describing when to run the checker and how to
  read each finding, plus `references/layering.md` recording the placement rules
  behind the tool: the four layers, one-rule-one-layer, the three gates for the
  always-on layer, the instruction budget, why `@path` imports do not save
  context, and the three situations where conditional loading silently fails.

### Design decisions

- **Coverage is reported, never judged.** The first implementation warned above a
  50% match rate. Testing against a real project proved that wrong: a frontend
  rule covering `web/` and `app/` while correctly excluding `src/` matched 51% of
  the tree and was exactly right. The rule that replaced it: what matters is
  whether a pattern *discriminates* between projects — 29% in one and 0% in
  another means precise, above half in *every* project means always-on in
  disguise. That judgment needs a human, so the tool prints numbers and stops.
- **The hook is silent by default.** A hook that prints on every edit trains
  everyone to ignore it. Silence means no problem.
- **Exit 2, not exit 1.** A `PostToolUse` hook's stderr on exit 0 is invisible to
  Claude. Exit 2 is the only way a post-run hook makes itself heard.
- **Fails first.** Every FAIL branch is exercised against a deliberately broken
  rule set before release. A gate that is green on its first run has proven
  nothing.

[Unreleased]: https://github.com/mi4646/claude-rules-lint/compare/v1.0.1...HEAD
[1.0.1]: https://github.com/mi4646/claude-rules-lint/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/mi4646/claude-rules-lint/releases/tag/v1.0.0
