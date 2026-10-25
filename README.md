# claude-rules-lint

Structural lint for layered `CLAUDE.md` rule sets.

Once you split instructions across `CLAUDE.md` and `.claude/rules/*.md`, three failures become possible and **all of them are silent** — nothing errors, Claude simply stops reading a rule you thought it had:

- a rule file that no `CLAUDE.md` indexes, so the agent never learns it exists
- a reference to a rule file that was renamed or deleted
- `paths:` frontmatter written but empty, so conditional loading never fires

This plugin catches those, keeps an eye on the 200-line adherence budget, and reports `paths:` coverage without judging it.

## Install

```bash
/plugin marketplace add mi4646/claude-rules-lint
/plugin install claude-rules-lint@claude-rules-lint
```

## Use

Ask Claude to "lint the CLAUDE.md rules", or run it directly:

```bash
python3 ~/.claude/plugins/*/claude-rules-lint/*/scripts/check-rules.py . --all
```

```bash
check-rules.py                 # check the current directory
check-rules.py <dir> [<dir>..] # check specific projects
check-rules.py --all           # also check ~/.claude (global layer)
check-rules.py --quiet         # FAIL only
```

Exit `0` = clean, `1` = at least one FAIL, `2` = usage error.

## What it checks

| Level | Finding |
|---|---|
| FAIL | rule file not referenced from the main `CLAUDE.md` |
| FAIL | main file references `rules/<x>.md` that does not exist |
| FAIL | `paths:` present but lists no patterns |
| FAIL | `.claude/rules/` exists with no `CLAUDE.md` to index it |
| WARN | main `CLAUDE.md` past 200 lines |
| INFO | per-rule `paths:` coverage and the top-level dirs it reaches |

## The automatic hook

`hooks/hooks.json` registers a `PostToolUse` hook on `Write|Edit|MultiEdit`. After an edit to a `CLAUDE.md` or a `.claude/rules/*.md`, it lints that project and — **only when something is wrong** — surfaces the findings to Claude via exit code 2, which is how a `PostToolUse` hook makes itself heard after the tool has already run.

Edits to any other file cost nothing: the hook resolves the path, exits 0, and stays silent. A hook that talks on every edit trains you to ignore it.

To turn it off, delete `hooks/hooks.json` (or install without the plugin and copy only `scripts/`).

## Coverage is reported, not judged

A rule covering 50% of a repo is not automatically wrong. A frontend rule that owns `web/` and `app/` while correctly excluding `src/` can sit above half and be exactly right.

What matters is whether the pattern **discriminates**. Measure one rule across two different projects: 29% here and 0% there means precise. Above half in *every* project means it is always-on in disguise and should drop its `paths:` — but that judgment needs a human, so the tool prints the numbers and the directories covered, and stops there.

## What it cannot catch

Prose quality. Vague rules, contradictory rules, duplicated guidance, stale rules — the tool is blind to all of it. Screen those by review; `skills/rules-lint/references/layering.md` records the placement rules that prevent most of them.

## Design notes

- **Zero dependencies.** `check-rules.py` is standard-library Python 3.9+.
- **Fails first.** Every FAIL branch is exercised against a deliberately broken rule set before release; a gate that is green on its first run has proven nothing.
- **Silent by default.** No output means no problem.

## License

MIT
