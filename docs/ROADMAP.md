# Technical Roadmap (2026-Q2)

## 1. Modular Architecture Evolution
Objective: Decouple crawling, processing, and storage to allow independent scaling.

### 1.1 Event-Driven Decoupling
- **Current**: Scrapy Pipelines directly write to Postgres/Redis.
- **Target**:
    - **Crawler**: Pushes raw HTML/JSON to **Kafka/RabbitMQ** (Topic: `raw_content`).
    - **Processor (New)**: Consumes `raw_content`, runs NLP/Classification, pushes to `processed_events`.
    - **Storage (New)**: Consumes `processed_events` and writes to Postgres/MinIO.
- **Benefit**: Crawlers never block on DB writes; Processors scale based on CPU load.

### 1.2 Service Mesh
- Isolate `Intelligence Operators` (Geo, Source Classifier) into standalone Microservices (gRPC/HTTP).
- Enables polyglot development (e.g., rewriting heavy NLP in Rust/Go).

## 2. Configuration Management
Objective: Zero-downtime reconfiguration.

### 2.1 Externalized Config
- Migrate `settings.py` constants to **Consul** or **Etcd**.
- **Dynamic Parameters**:
    - `CONCURRENT_REQUESTS`
    - `DOWNLOAD_DELAY`
    - `User-Agent` Rotation Pools
- **Hot-Reload**: Implement a sidecar or polling thread to update runtime config without restarting containers.

## 3. Observability & Monitoring
Objective: Real-time visibility into the "Black Box".

### 3.1 Metrics Stack (Prometheus + Grafana)
- **Exporters**:
    - `scrapy-prometheus-exporter`: Detailed spider metrics.
    - `postgres_exporter`: DB pool health.
    - `node_exporter`: System resources.
- **Key Dashboards**:
    - **Spider Health**: Success Rate, Latency P95/P99, ScrapyErr Breakdown.
    - **Business Logic**: Articles/Minute, Entity Extraction Rate, Geo-diversity Entropy.

### 3.2 Alerting (Alertmanager)
- **P0 (Critical)**: Success Rate < 80% for > 15min.
- **P1 (High)**: DB Connection Pool saturation > 90%.
- **P2 (Warning)**: Unusual spike in 403/429 errors.

## 4. Data Quality Assurance
Objective: Trustworthy data for scientific analysis.

### 4.1 Automated Validation
- **Schema Validation**: Strict Pydantic models at ingestion.
- **Integrity Checks**:
    - **Completeness**: Warn if `content` is empty but `title` exists.
    - **Duplication**: SimHash comparison window (7 days).
    - **Timeliness**: Alert if `published_at` lag > 4 hours.

## 5. Engineering Standards
Objective: Maintainable, research-grade code.

### 5.1 Code Review Checklist
- **Error Handling**: No bare `except Exception`. All errors must be logged with context.
- **Performance**: No N+1 queries. Heavy compute must be async/threaded.
- **Testing**:
    - Unit Test Coverage > 80%.
    - Integration Tests for all external APIs (Media Cloud, etc.).
- **Documentation**: All public methods must have docstrings (NumPy style).

### 5.2 CI/CD Gates
- **Linting**: Ruff/Black enforced.
- **Security**: `bandit` scan for secrets and vulnerabilities.
- **Regression**: Replay recorded "Golden Scrape" sessions to verify parser stability.
