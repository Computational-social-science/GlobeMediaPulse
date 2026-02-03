# Technical Maintenance & Migration SOP

**Date:** February 3, 2026  
**Version:** 1.0  
**Authors:** System Architect & Engineering Team  
**Scope:** Frontend Stability, Crawler Persistence, and Long-Term Operations

---

## 1. Frontend Runtime Error Diagnosis & Remediation

### 1.1 Root Cause Analysis
- **Incident:** `ERR_CONNECTION_REFUSED` on `localhost:5173`.
- **Diagnosis:** The Vite development server was not active. This is a blocking environmental error, not a code defect.
- **Resolution:**
  - Validated `npm install` for dependencies.
  - Executed `npm run dev` to bind `0.0.0.0:5173`.
  - Verified accessibility via local network.

### 1.2 Error Monitoring Implementation (Sentry)
To move beyond reactive fixes, we have integrated **Sentry** for real-time error tracking.
- **Library:** `@sentry/svelte`
- **Configuration:** initialized in `src/main.js`.
- **Capabilities:**
  - **Tracing:** 100% sample rate for performance bottlenecks.
  - **Replay:** 10% session recording for reproduction (100% on error).
- **Action Required:** Update `YOUR_SENTRY_DSN` in `src/main.js` with the production key.

### 1.3 Test Coverage Strategy
- **Target:** >80% coverage.
- **Action:** Continue adding E2E tests in `e2e/` folder using Playwright (e.g., `sidebar-visual.spec.ts` exists).

---

## 2. Docker Crawler Persistence & Migration Plan

### 2.1 Containerization Strategy
We have transitioned from a raw Python process to a robust Docker orchestration.
- **New Artifacts:**
  - `backend/Dockerfile.crawler`: Optimized image specifically for Scrapy, stripping unnecessary web server dependencies.
  - `docker-compose.yml`: Root-level orchestration with auto-restart policies.
  - `backend/scripts/start_crawler.sh`: Intelligent entrypoint script.

### 2.2 Persistence & Breakpoint Resumption
To ensure zero data loss during restarts or crashes:
- **Mechanism:** Scrapy `JOBDIR` persistence.
- **Implementation:**
  - The `start_crawler.sh` script checks for an existing job directory at `/app/crawlers_jobdir`.
  - If found, it resumes the crawl using `scrapy crawl ... -s JOBDIR=...`.
  - Docker Volume: `./data/crawler_persistence` maps to `/app/crawlers_jobdir`.
- **Benefit:** The crawler can be stopped (SIGINT) or crash, and upon restart, it resumes from the last seen request.

### 2.3 Migration to Free Cloud Tier (e.g., AWS Free Tier / Oracle Cloud)
**Plan:**
1.  **Prepare:** Ensure `docker-compose.yml` and `data/` folder are ready.
2.  **Provision:** Launch a free-tier VM (Ubuntu 22.04 LTS recommended).
3.  **Deploy:**
    ```bash
    # On remote server
    git clone <repo_url>
    cd GlobeMediaPulse
    # Create .env file with secrets
    docker-compose up -d --build
    ```
4.  **Verify:** Check logs via `docker-compose logs -f crawler`.

---

## 3. Long-Term Architecture & Operations (DevOps)

### 3.1 Scheduling (APScheduler)
For high-availability scheduling without external dependencies:
- **Recommendation:** Integrate `APScheduler` (Advanced Python Scheduler) directly into the backend `main.py` or a dedicated worker.
- **Why:** Free, Python-native, handles cron-style triggers, and avoids the complexity of Airflow for this scale.

### 3.2 CI/CD Pipeline (GitHub Actions)
**Workflow:**
1.  **Push to Main:** Triggers unit tests (`pytest`) and linting (`eslint`).
2.  **Release Tag:** Builds Docker images and pushes to GHCR (GitHub Container Registry).
3.  **Deploy:** SSH action pulls new image on cloud server and runs `docker-compose up -d`.

### 3.3 Monitoring & Alerting Specification
- **Service Liveness:** Docker Healthcheck (`pgrep -f scrapy`) auto-restarts dead containers.
- **Resource Usage:** Prometheus/Grafana (optional) or simple `docker stats` logging.
- **Business Metrics:**
  - **Crawler Yield:** Articles scraped per hour (log parsing).
  - **Error Rate:** Scrapy error log count > threshold triggers email/Slack alert.

### 3.4 Quarterly Milestones
| Quarter | Objective | Deliverables |
| :--- | :--- | :--- |
| **Q1** | **Stabilization** | Docker migration, Sentry integration, 80% Test Coverage. |
| **Q2** | **Expansion** | Integrate 50+ Global South sources, Geolocation F1 > 0.95. |
| **Q3** | **Intelligence** | NLP Pipeline v2 (Entity Linking), Automated Topic Clustering. |
| **Q4** | **Scale** | Kubernetes migration (if data > 1TB), Public API Release. |

---

## 4. Maintenance SOP

### 4.1 Backup
- **Frequency:** Daily.
- **Command:** `tar -czf backup_$(date +%F).tar.gz ./data/output ./data/crawler_persistence`
- **Storage:** S3 or separate drive.

### 4.2 Log Rotation
- **Configured in:** `docker-compose.yml` (max-size: 10m, max-file: 3).
- **Manual Cleanup:** `find ./data/logs -name "*.log" -mtime +30 -delete`

### 4.3 Disaster Recovery
1.  **Clone Repo** on new server.
2.  **Restore Data** from latest backup tarball.
3.  **Start Services:** `docker-compose up -d`.
4.  **Verify:** Check `docker ps` and tail logs.
