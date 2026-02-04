# Next Phase Plan (Q2 2026)

**Focus:** Platform Stability & Research Capabilities  
**Status:** Planning

---

## 1. Core Stability (Weeks 1-4)
- [ ] **Sentinel Enhancement:** Improve Windows compatibility for `sentinel.py` (JSON parsing).
- [ ] **Docker Optimization:** Implement multi-stage builds to reduce image size < 500MB.
- [ ] **Database Tuning:** Enable `pg_stat_statements` and optimize crawler query patterns.

## 2. Research Features (Weeks 5-8)
- [ ] **Advanced Geoparsing:** Integrate `cliff-clavin` or similar NLP service for city-level precision.
- [ ] **Data Export:** Add "Download CSV" button for filtered datasets in the dashboard.
- [ ] **Custom Spiders:** UI for researchers to add simple XPath-based scrapers without coding.

## 3. Infrastructure (Weeks 9-12)
- [ ] **Cloud Migration:** Prepare Terraform scripts for AWS/Azure deployment.
- [ ] **Monitoring Dashboard:** Deploy Grafana + Prometheus for long-term metrics.
