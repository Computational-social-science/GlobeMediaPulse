# Next Phase Action Plan: Optimization & Expansion (Q2 2026)

**Objective:** Transform the stabilized prototype into a robust, multi-source intelligence platform with high data quality and automated operations.

---

## 1. Optimization Goals

### 1.1 Data Expansion (Global South Focus)
- **Target:** Increase source count from current pilot set to **50+ high-quality sources**.
- **Focus Regions:** Sub-Saharan Africa, Southeast Asia, Latin America.
- **Quality Gate:** Maintain extraction success rate > 95% per source.

### 1.2 Geolocation Precision
- **Target:** Elevate Location Extraction Macro-F1 Score to **≥ 0.95**.
- **Methodology:**
  - Integrate IP-based geolocation fallback.
  - Implement Named Entity Recognition (NER) fine-tuning on domain-specific news corpus.
  - Expand Golden Test Set to 20k samples.

### 1.3 System Resilience
- **Target:** Achieve **99.9% Uptime** for Crawler Service.
- **Methodology:**
  - Fully migrated Docker-based cloud deployment.
  - Automated "Circuit Breaker" for banning domains (stop crawling if 403 rate > 50%).
  - Real-time alerting via Slack/Discord webhooks.

---

## 2. Resource Needs Assessment

### 2.1 Infrastructure (Cloud)
| Resource Type | Specification | Estimated Cost | Justification |
| :--- | :--- | :--- | :--- |
| **Compute** | 2x vCPU, 4GB RAM (e.g., AWS t3.medium or Oracle Free Tier Ampere) | Free / $20/mo | Scrapy concurrency & NLP lightweight inference. |
| **Storage** | 100GB SSD (Block Storage) | $10/mo | Postgres DB (Text Data) & Logs. |
| **Network** | Static IP | $3/mo | Stable whitelisting for target sites. |

### 2.2 Development
- **Personnel:** 1 Full-stack Engineer (50% allocation), 1 Data Scientist (30% allocation).
- **Tooling:** Sentry (Free Tier), GitHub Actions (Free Tier).

---

## 3. Risk Management & Contingency

| Risk Category | Risk Description | Probability | Impact | Mitigation Strategy |
| :--- | :--- | :--- | :--- | :--- |
| **Technical** | Target sites implement strict anti-bot measures (Cloudflare, CAPTCHA). | High | High | Implement `undetected-chromedriver` or rotating proxies (BrightData/Smartproxy - budget needed). |
| **Data** | Database grows beyond single-node capacity. | Medium | Medium | Implement table partitioning by month; Plan migration to Managed SQL or TimescaleDB. |
| **Legal** | Copyright complaints from news publishers. | Low | Critical | Enforce `robots.txt` strictly; Implement "Opt-out" mechanism; Only store summaries/metadata, not full text if required. |

---

## 4. Milestone Acceptance Criteria

### Milestone 1: Cloud Migration Complete (Week 2)
- [ ] Crawler running in Docker on remote server.
- [ ] Persistence confirmed (restart test).
- [ ] CI/CD Pipeline active (auto-deploy on push).

### Milestone 2: Data Quality Upgrade (Week 6)
- [ ] 50+ Sources active.
- [ ] Macro-F1 >= 0.95 verified by CI job.
- [ ] Deduplication logic operational (SimHash).

### Milestone 3: Public Beta Readiness (Week 12)
- [ ] Public API documented (Swagger/OpenAPI).
- [ ] Frontend dashboard load time < 1.5s (P95).
- [ ] Full disaster recovery drill completed.
