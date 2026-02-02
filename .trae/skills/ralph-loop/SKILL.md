---
name: "ralph-loop"
description: "Applies a strict Reflect→Ask→Run→Log→Patch loop for reliable iteration. Invoke when debugging flaky dev env, sync issues, or nightly crawler failures."
---

# Ralph Loop

## Intent

Drive a deterministic iteration cadence for systems that drift (local services, remote deploys, CI/CD, long-running crawlers).

## Loop Steps

1. **Reflect**
   - State the failure mode in one sentence.
   - Define a measurable success condition.

2. **Ask (internally)**
   - Which subsystem owns the failure?
   - What is the smallest observable that disambiguates the top hypotheses?

3. **Run**
   - Execute the minimal command(s) that surface the observable.
   - Prefer health endpoints and status commands over log spelunking.

4. **Log**
   - Record the decisive signal (exit code + key lines).
   - Note the “why” in terms of invariants and drift.

5. **Patch**
   - Encode a fix into automation or config.
   - Add a verification gate so this failure cannot silently recur.

## Success Criteria

The loop completes only when:

- The failure is no longer reproducible under the same trigger.
- A verification gate exists (script/command) that would fail if the issue returns.

