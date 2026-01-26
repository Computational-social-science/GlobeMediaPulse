# Task Plan: Distributed Crawler & System Enhancement

**Goal:** Stabilize the distributed crawler, enhance system capabilities with MCP-like integrations (PostgreSQL/GitHub), implement monitoring/analytics, and optimize the Docker development environment.

## Phase 1: Planning & Stabilization
- [x] Create `task_plan.md` (This file).
- [x] Fix Spacy/Pydantic schema error blocking the crawler (Patched Pydantic V1).
- [x] Optimize `UniversalNewsSpider` settings (Concurrency, Playwright usage).
- [x] Verify `UniversalNewsSpider` functionality with Redis (via `scrapy list`).
- [x] Document findings in `findings.md`.
- **Status:** completed

## Phase 2: Infrastructure Enhancement (MCP-style)
- [x] Enhance PostgreSQL integration: Ensure robust connection pooling and error handling in `database.py`.
- [x] Check GitHub Actions integration: Ensure workflows are correctly set up for deployment and CI.
- **Status:** completed

## Phase 3: Monitoring & Analytics
- [x] Implement `manage.py` CLI with `--analytics` and `--health-check`.
- [x] Add analytics logic (e.g., crawl rates, error rates) to the CLI.
- [x] Implement health checks for DB, Redis, and Crawler connectivity.
- [x] Add `crawl` command to `manage.py`.
- **Status:** completed

## Phase 4: Docker & Dev Environment Optimization
- [x] Verify Docker Compose stack (Backend, Frontend, Redis, Postgres).
- [ ] Test hot-reloading in the containerized environment.
- [x] Ensure `devcontainer.json` provides a seamless VS Code experience.
- **Status:** in_progress

## Phase 5: Verification & Delivery
- [ ] Run full system test (crawl -> process -> save).
- [ ] Verify frontend data visualization.
- [ ] Deliver final report.
- **Status:** pending
