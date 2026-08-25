---
name: ddd-review
description: Analyze a git diff or PR and produce a structured code review report, calibrated to quiz-management's DDD layering and port pattern
argument-hint: "[branch|#123|commit-range] [--high-only] [--fresh]"
allowed-tools: Bash(git *), Bash(gh *)
---

Analyze a git diff or GitHub PR and produce a structured code review report. Supports iterative reviews via `.claude/reviews/`.

This is the project-local counterpart to the global `/code-review` skill: same underlying idea, but calibrated specifically to this project's DDD layers, the port pattern (`CLAUDE.md` rule 2), and its persisted-state diffing across review runs. Use it when you want a review checked against this project's own rules; use `/code-review` for the general-purpose multi-level flow.

## Step 1 — Parse input

`$ARGUMENTS` controls review scope. Accepted formats:

1. **No arguments**: Review all uncommitted changes.
2. **Branch name** (e.g. `feature/add-tenant-scoping`): Review branch diff vs `main`.
3. **PR number** (e.g. `#123`): Fetch with `gh pr diff 123`.
4. **Commit range** (e.g. `abc123..def456`): Review that range.
5. **Flag `--high-only`**: Only report High severity findings.
6. **Flag `--fresh`**: Ignore previous review state.

## Step 2 — Collect diff and context

Gather the diff based on the source:

| Source | Command |
|--------|---------|
| Uncommitted | `git diff HEAD` |
| Branch | `git diff main...<branch>` |
| PR | `gh pr diff <number>` |
| Commit range | `git diff <range>` |

If empty, abort: "No changes found."

Map changed file paths to layers:

| Path pattern | Layer |
|-------------|-------|
| `src/*/domain/entities/` | Domain — entities |
| `src/*/domain/repositories/` | Domain — repository ports (ABCs) |
| `src/*/domain/exceptions.py` | Domain — exceptions |
| `src/*/application/*/dto.py` | Application — DTOs |
| `src/*/application/*/use_case.py` | Application — use cases |
| `src/*/application/*/*_service.py` | Application — domain services |
| `src/*/infrastructure/persistence/django/models/` | Infrastructure — Django models |
| `src/*/infrastructure/repositories/*_imp.py` | Infrastructure — repository impls (port producers) |
| `src/*/infrastructure/event_handlers/` | Infrastructure — event handlers |
| `src/*/presentation/schema/mutations/` | Presentation — GraphQL mutations |
| `src/*/presentation/schema/{inputs,responses,types}/` | Presentation — GraphQL contracts |
| `src/*/presentation/admin/` | Presentation — Django admin |
| `src/shared/**` | Shared — cross-cutting |
| `tests/**` | Tests (infer layer from the mirrored path under `tests/<app>/...`) |

Read the full current version of each changed file.

## Step 3 — Load previous review state

Determine **review key**: `pr-<N>`, `branch-<name>`, `range-<start>-<end>`, or `uncommitted`.

If `.claude/reviews/<key>.md` exists and `--fresh` not set: read and parse previous findings for comparison in Step 5. Match by `file_path` + `short_description_slug`.

## Step 4 — Analyze changes

Read `.claude/skills/review-checklist/SKILL.md` for the categories, severities, and pre-analysis verification rules.

Launch the `code-reviewer` agent (Agent tool, `subagent_type: "code-reviewer"`) with a self-contained prompt containing: the collected diff, the full current content of each changed file, the layer mapping from Step 2, and the checklist categories/severities/pre-analysis rules from `review-checklist`. Ask it to apply all categories to every changed file and return findings with severity, file, line, and a concrete suggestion. A fresh agent has no memory of this conversation — the prompt must carry everything it needs, it cannot be told to "read the checklist" and expected to know the path unprompted (though it may re-read the file itself if given the path).

## Step 5 — Compare with previous review

If previous findings loaded:

1. Issue no longer present in code → `FIXED`
2. Issue still exists → `OPEN`
3. New issue not in previous → `NEW`

If no previous state, all findings are implicitly new (no status tag).

## Step 6 — Generate report

### Iteration header (only when previous state exists)

```
Fixed: <N>  |  Open: <N>  |  New: <N>
```

List FIXED findings first, then per-file sections sorted by severity:

```
File: `<file_path>`

  [HIGH]   L<line>: <description>  {OPEN}
           Suggestion: <concrete fix>
```

### Summary

```
REVIEW SUMMARY
Files reviewed:       <N>
Files with findings:  <N>
High severity:        <N>
Medium severity:      <N>
Low severity:         <N>
Verdict: <APPROVE | REQUEST CHANGES | COMMENT>
```

Verdict: **APPROVE** (No High, ≤2 Medium), **REQUEST CHANGES** (Any High), **COMMENT** (No High, 3+ Medium).

## Step 7 — Persist review state

Save to `.claude/reviews/<key>.md`:

```markdown
<!-- ddd-review state — do not edit manually -->
<!-- date: YYYY-MM-DD -->
<!-- source: <diff source> -->

| Status | Severity | File | Line | Slug | Description |
|--------|----------|------|------|------|-------------|
| OPEN | HIGH | src/quiz/presentation/schema/mutations/mutations_admin.py | 31 | operation-id-server-generated | operation_id built with uuid.uuid4() instead of read from context |
```

Include all current OPEN + all previous FIXED findings. Overwrite on each run.

## Rules

1. **Review state is the only side effect.** Do not modify source code.
2. **Evidence-based.** Every finding must reference a specific line with a concrete problem.
3. **No false positives over no false negatives.** If uncertain, omit. Read decorator/mixin implementations before flagging.
4. **Respect project conventions.** Judge against `CLAUDE.md`/`docs/claude/*.md`, not generic best practices.
5. **Single responsibility.** Reviews only. For follow-up work, suggest fixing directly or opening an `openspec-explore` conversation for anything bigger than a one-line fix.
6. **Actionable suggestions.** Imperative language: "Move validation to the domain entity's `__post_init__`."
7. **No severity inflation.** Use checklist severity levels as-is.
8. **Complete report.** Always include per-file sections, summary, and verdict.
