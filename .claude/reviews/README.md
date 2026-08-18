# Review state

Persisted findings from the `ddd-review` skill (`.claude/skills/ddd-review/`), one file per review key (`pr-<N>`, `branch-<name>`, `range-<start>-<end>`, `uncommitted`). Each run reads the matching file to diff against the previous pass (FIXED/OPEN/NEW) and overwrites it with the current findings.

Generated and overwritten by the skill — don't edit these by hand.
