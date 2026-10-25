# Layering rules: where a rule belongs

> The reasoning behind `check-rules.py`. Read this before restructuring a rule set.

## 1. The four layers

```
~/.claude/CLAUDE.md         judgment layer   — always on. What must happen, never how
~/.claude/rules/*.md        detail layer     — no `paths:` = always on; with `paths:` = on demand
<project>/CLAUDE.md         facts layer      — this project's architecture, commands, traps only
<project>/.claude/rules/    project detail   — domain traps, loaded by `paths:`
```

## 2. One rule, one layer

**A rule lives at the highest layer where it is still true — and nowhere else.**

Layers **add up**, they do not override. Claude Code's documentation is explicit: if a user-level rule and a project-level rule conflict, "Claude may follow either one". Duplication is therefore not redundancy — it converts a decision into a coin flip.

| The rule... | Lives in | The other layer carries |
|---|---|---|
| Is true for anything you build | judgment layer | **nothing** — not even a pointer |
| Is a judgment, but its landing differs per project | judgment → global, landing → project | the project side writes the landing only, never restates the judgment |
| Is specific to one project | project layer | — |

## 3. Three gates before a rule enters the always-on layer

All three must hold. One miss sends it down to the detail layer.

1. **The consequence is severe** — security, money, data loss, silent leakage, rework.
2. **No automatic check would catch it** — if the compiler, the type checker, the linter or the tests already fail on it, it should not spend always-on budget.
3. **The trigger is scattered** — it cannot be reached reliably by opening a directory. If a directory reliably reaches it, give it `paths:` instead.

## 4. The budget is real

Roughly **150–200 instructions** is what frontier models follow reliably ([IFScale](https://arxiv.org/abs/2507.11538)), and the system prompt already spends about 50 of them. Official guidance flags instruction files past 200 lines as possibly reducing adherence. To add a rule, delete or demote one.

This is why `check-rules.py` warns at 200 lines rather than staying silent.

## 5. Why `@path` imports do not save context

Official documentation: splitting into `@path` imports "helps organization but doesn't reduce context, since imported files load with the CLAUDE.md importing them."

Only two mechanisms actually reduce what loads:

| Mechanism | Enters context | Fits |
|---|---|---|
| `rules/*.md` with no `paths:` | every session | the few hard constraints you must always hold |
| `rules/*.md` with `paths:` | when a matching file is read/edited | stack-specific detail |
| skills | when the description matches or it is invoked | multi-step procedures |

## 6. Conditional loading fails in three situations

`paths:` rules are injected when Claude reads, writes, or edits a matching file. They are **not** injected when:

- the edit follows a search and a direct change,
- only a local substitution is made,
- or a **new file** is created.

So every rule set that relies on `paths:` must tell the agent: *if you are about to touch what this table lists and the rule body is not in context, read it yourself.* That escape hatch is not optional.

## 7. Keep the index two-way

Every rule file must appear in the main `CLAUDE.md`, and every reference in the main file must resolve. A file nobody indexes is invisible; a reference that resolves to nothing sends the reader hunting. Both are FAILs in `check-rules.py` for exactly that reason.

## 8. Adding a rule without adding a check

An instruction is advisory and gets skipped under load; a gate does not. If a structural mistake can recur, extend the tool rather than restating the rule in prose. The one exception is a rule whose violation is silent *and* unmeasurable — that one earns its place in the always-on layer, and is worth the budget.
