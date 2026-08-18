---
name: review-checklist
description: Standard code review analysis categories with severity assignments for quiz-management
user-invocable: false
---

## Purpose
Define standard code review analysis categories with severity assignments, calibrated to quiz-management's DDD layering and port pattern (see `CLAUDE.md` and `docs/claude/mandatory-patterns.md`).

## Input
- Changed files from a diff (provided by the calling skill).

## Output
- Per-file findings with severity (High/Medium/Low), line references, and concrete suggestions.
- Verdict: APPROVE, REQUEST CHANGES, or COMMENT.

## What to avoid
- Do not collect diffs — that is the caller's job.
- Do not publish comments or modify code.

Apply to every changed file in a diff.

## Pre-analysis verification (mandatory)

Before reporting any finding, verify it is real:

- **Decorator/mixin guarantees**: If code relies on `@handle_mutations_exceptions`, `@async_database()`, or a base mixin, read its implementation before flagging something it already covers.
- **Project-wide patterns**: Before flagging a pattern as wrong, check if the same pattern exists in 2+ other files in the same layer. If it does, it's a project convention — do not flag it.
- **Reachability**: Before flagging a code path as unreachable or a union member as unnecessary, verify by reading all exception paths. Only flag if provable.
- **Intentional asymmetries**: `async def` on a repository ABC vs. `@async_database()`-wrapped sync `def` on its impl is correct by convention, not a mismatch. `Entity.from_model()` exists without a symmetric `to_model()` — also intentional (inlined in the repo impl instead).

## Categories

### 1 — Bugs and correctness (High)

- Null/None dereference without guard
- Off-by-one errors, incorrect boundary conditions
- Missing `await` on async calls
- Wrong variable used (copy-paste errors)
- Incorrect type comparisons or casting
- Missing return statements or unreachable code
- Race conditions or shared mutable state issues
- Exception raised that doesn't subclass the right base in `src/shared/domain/exceptions.py`'s hierarchy (`DomainError` → `NotFoundError`/`ApplicationError`/`InfrastructureError`), so `@handle_mutations_exceptions` maps it to the wrong response type

### 2 — Security (High)

- SQL injection (raw string interpolation in queries)
- Missing or wrong `permission_classes` on a GraphQL mutation/query (`IsAuthenticated`, `IsAdmin`, `IsStaff`, `IsOrganizationUser`)
- Sensitive data exposure in error messages or logs
- Command injection via unsanitized input
- Missing input validation at system boundaries

### 3 — Architecture violations (High)

Verify against `CLAUDE.md`'s "Mandatory patterns and rules" and `docs/claude/mandatory-patterns.md`. Focus on:

- **Rule 1 (bulk writes)**: `.create()`/`.save()` called inside a loop instead of pre-generating UUIDs and `bulk_create()`-ing once.
- **Rule 2 (port pattern)**: an app importing another app's Django models directly (`from src.<other_app>.infrastructure...models import ...`) instead of going through a `domain/repositories/*Repository` ABC implemented by `infrastructure/repositories/*_repository_imp.py`. Also flag: an ABC's port gaining a method its impl doesn't have, or vice versa.
- **Rule 3 (`operation_id`)**: generated server-side (e.g. `uuid.uuid4()` in a resolver) instead of read from `info.context.operation_id` / the client's `X-Operation-ID` header. Always High — breaks idempotency.
- **Rule 4 (mutation exception handling)**: a mutation with manual `try/except` instead of `@handle_mutations_exceptions`.
- **Entity/DTO convention**: an entity that isn't `@dataclass(frozen=True)` with `__post_init__` validation, or a DTO that isn't a frozen Pydantic `BaseModel`.
- **Repository naming/placement**: ABC not in `domain/repositories/`, or impl not named `*RepositoryImpl` under `infrastructure/repositories/*_repository_imp.py`.

### 4 — Performance (Medium)

#### 4a — SQL and database
- N+1 query patterns
- Missing database indexes for columns used in filters or joins
- Unbounded queries without pagination or limit
- Unnecessary eager loading of large relations
- Redundant queries (same data fetched multiple times)
- ORM writes in a loop instead of `bulk_create()` (see Category 3, Rule 1 — report once, under Architecture, not twice)

#### 4b — Application-level hotspots
- Repeated domain method calls with identical arguments inside loops (memoize in the use case)
- O(n*m) lookups that could be O(n) with a dict/set pre-index
- Expensive object construction repeated per iteration when the result is identical

### 5 — Interfaces and contracts (Medium)

- A repository impl (`infrastructure/repositories/*_repository_imp.py`) with a public method not declared on its ABC port (`domain/repositories/*Repository`)
- A port method the impl doesn't implement
- Method signatures drifting between ABC and impl beyond the intentional async/sync convention (see Pre-analysis verification)
- New public repository method added without updating the port it's supposed to satisfy

### 6 — GraphQL anti-patterns (Medium)

Verify against `CLAUDE.md`'s mandatory rules 3–4 and the GraphQL response pattern in `docs/claude/code-style.md`. Check for:

- Missing `operation_id` in a mutation's response payload
- Mutation input not modeled as a `@strawberry.input`
- Missing or incomplete error-type members in the response union (should map to `ValidationErrorResponse`/`IntegrityErrorResponse`/`InternalErrorResponse` per the decorator's mapping)
- A GraphQL type missing its `Entity.from_model()` conversion
- Missing `permission_classes` on a mutation/query that should require one

### 7 — Missing tests (Medium)

- New use case or mutation without corresponding test coverage
- New domain entity or validation rule without a unit test
- Changed business logic without updated tests
- New error paths without test coverage

### 8 — Code quality (Low)

- Dead code or unused imports
- Inconsistent naming conventions (see `CLAUDE.md`'s naming table)
- Duplicated logic that should be extracted
- Missing type annotations on public interfaces
- Overly complex functions
- Docstring added without a non-obvious WHY (project convention: only when the WHY isn't obvious from the signature), or not formatted Google-style (`Args:`/`Returns:`/`Raises:`) when one is warranted

## Finding format

```
[<SEVERITY>] L<line>: <description>
Suggestion: <concrete fix in imperative form>
```

## Verdict criteria

- **APPROVE**: No High findings, 2 or fewer Medium.
- **REQUEST CHANGES**: Any High finding exists.
- **COMMENT**: No High findings, but 3+ Medium.
