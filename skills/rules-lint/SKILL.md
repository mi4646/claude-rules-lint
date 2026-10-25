---
name: rules-lint
description: Structural lint for layered CLAUDE.md rule sets. Use when the user asks to check, lint, audit, or validate CLAUDE.md files, .claude/rules/ files, rule layering, or "why isn't Claude reading my rules". Catches rule files nothing indexes, references to rules that no longer exist, empty `paths:` frontmatter, and a main file past its adherence budget.
tools: Read, Glob, Grep, Bash
---

# rules-lint

Checks the **structure** of a layered rule set — not the quality of its prose.

## When to run

- The user asks to check / audit / validate `CLAUDE.md` or `.claude/rules/`.
- The user says a rule "isn't being followed" — a missing index entry is the most common cause and is invisible by reading.
- You just added, renamed, or deleted a rule file.

## Run it

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/check-rules.py <project-dir> [<dir>...] [--all] [--quiet]
```

- No args → checks the current working directory.
- `--all` → also checks `~/.claude` (the global layer).
- `--quiet` → FAIL only.

Exit code `0` = no FAIL, `1` = at least one FAIL, `2` = usage error.

## What each finding means

| Level | Finding | Fix |
|---|---|---|
| **FAIL** | rule file not referenced from the main `CLAUDE.md` | Add it to the index table — an unreferenced rule is one the agent will never know to read |
| **FAIL** | main file references `rules/<x>.md` that does not exist | Correct the name or delete the reference |
| **FAIL** | `paths:` frontmatter present but lists no patterns | Add patterns or drop the frontmatter to make it always-on |
| **FAIL** | `.claude/rules/` exists with no `CLAUDE.md` | Add the main file with an index |
| **WARN** | main `CLAUDE.md` over 200 lines | Move detail into a rule file; frontier models follow ~150–200 instructions reliably |
| **INFO** | per-rule `paths` coverage | **Not a defect.** See below |

## Coverage is reported, never judged

A high coverage rate is legitimate when the rule genuinely owns that much of the tree — a frontend rule covering `web/` and `app/` while correctly excluding `src/` can sit above 50% and be right.

What matters is whether the pattern **discriminates**: measure the same rule across two different projects. 29% here and 0% there means the pattern is precise. Above half in *every* project means the rule is effectively always-on and should drop its `paths:` — that is a human call, so the tool only reports the numbers and the top-level directories covered.

## What it cannot catch

Content quality. It will not notice vague rules, two rules that contradict each other, duplicated guidance, or rules that have gone stale. Those need review — see `references/layering.md` for the placement rules that prevent most of them.
