---
name: "superpowers"
description: "Runs a high-leverage dev loop (health, sync, deploy, verify). Invoke when you need one-click local+remote readiness or when GitHub/Fly drift appears."
---

# Superpowers

## Goal

Make the workspace behave like a continuously consistent system across:

1. Local stack (Docker Compose + dev UX)
2. Remote stack (Fly backend + crawler)
3. Publication surface (GitHub Pages frontend)

## When To Invoke

Invoke when any of the following happens:

- GitHub Pages shows stale UI or “days-old” behavior
- Fly crawler is not running, keeps dying, or shows degraded health
- Local + remote environment setup needs to be “one-click” reproducible
- You want a single, verified end-to-end sync before coding

## Execution Loop (R-A-L-P)

1. **R — Reflect**
   - Identify drift: local vs remote vs Pages.
   - Collect current status signals: health endpoints, crawler status, CI/workflow trigger expectations.

2. **A — Act**
   - Apply minimal changes that restore invariants:
     - Local services reachable
     - Remote health OK
     - Pages build pipeline triggers on relevant changes
     - Crawler starts and stays stable (or fails loudly with a root cause)

3. **L — Learn**
   - Convert the incident into a constraint:
     - e.g., “port drift makes 5174 non-durable”
     - e.g., “no push ⇒ no Pages deploy”

4. **P — Patch**
   - Encode the constraint into automation:
     - one command entrypoint
     - deterministic ports where possible
     - post-deploy verification gates

## Verification Gates

Treat the iteration as successful only if:

- Local: `/health/full` returns 200 and frontend is reachable
- Remote: `/health/full` returns 200 and crawler status aligns with policy
- Pages: a push to `main` affecting `frontend/**` triggers the deploy workflow

