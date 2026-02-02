# Globe Media Pulse: A Computational Observatory for the Global Media Ecosystem
> **Uncharted pulse of globe media**

**Status**: Active Development (v2.0 - "Snowball Discovery" Phase)

## 1. Scientific Motivation

In the digital information age, the structure of the global media landscape is not static but fluid and hierarchical. Traditional media monitoring relies on static, manually curated lists (seed libraries) which suffer from:
1.  **Selection Bias**: Over-representation of "Global North" outlets.
2.  **Decay**: Inability to track the rapid emergence of digital-native local sources (Tier-2).
3.  **Opaqueness**: Lack of transparency in how "influence" is defined.

**Globe Media Pulse** proposes a dynamic, algorithmic approach to mapping the global information ecosystem. By treating media outlets as nodes in a citation network, we employ **Snowball Sampling** initiated from high-authority "Super Nodes" (Tier-0) to automatically discover, classify, and monitor the long tail of local media (Tier-2).

This system serves as a foundational instrument for Computational Social Science, enabling real-time observation of information propagation, framing competitions, and the structural topology of global news.

---

## 2. Methodology & Algorithms

### 2.1 Tiered Media Stratification Strategy
We model the media ecosystem as a three-tier hierarchy based on influence scope and citation authority:
*   **Tier-0 (Global Super-Nodes)**: Transnational wire services and elite media (e.g., Reuters, AP, AFP). These serve as the "Ground Truth" seeds.
*   **Tier-1 (National Hubs)**: Dominant national broadcasters and newspapers (e.g., CCTV, BBC, Le Monde).
*   **Tier-2 (Local/Regional Nodes)**: The vast, dynamic layer of local reporting and specialized outlets.

### 2.2 Algorithmic Discovery (Snowball Sampling)
Instead of manual curation, we implement an automated discovery pipeline:
1.  **Ingestion**: Deep crawling of Tier-0/1 articles.
2.  **Extraction**: Parsing of citation outlinks from article bodies (not just navigation menus).
3.  **Voting Mechanism**: Unseen domains cited by multiple authoritative nodes accumulate "Citation Credits".
4.  **Promotion**: Candidates crossing a significance threshold are automatically promoted to the monitoring pool.

### 2.3 Structural Fingerprinting (SimHash)
To ensure data integrity and robust source identification:
*   We utilize **SimHash** to generate locality-sensitive hashes of website DOM structures.
*   This allows the system to detect:
    *   Site layout changes (indicating redesigns or ownership changes).
    *   Mirror sites and content farms (structural clones).
    *   Anti-scraping countermeasures.

---

## 3. System Architecture

The project adopts a **static-first, zero-cost** architecture for durable publishing, with an optional local full-stack mode for research development.

### 3.1 Backend Core (`/backend`)
*   **Framework**: FastAPI (Python 3.11+) for high-performance async orchestration.
*   **Crawling Engine**: Scrapy + Scrapy-Redis + Playwright.
    *   Distributed scheduling via Redis.
    *   Headless browser rendering for modern SPA websites.
*   **Intelligence Operators**: Modular units for Source Classification, Parsing, and Storage logic.
*   **Data Hygiene**: Strict "Metadata Only" storage policy. Article bodies are processed for metadata/links and then discarded to respect privacy and copyright.

### 3.2 Frontend Visualization (`/frontend`)
*   **Framework**: Svelte + Vite + D3.js.
*   **Real-time Interactivity**: WebSocket connections to the backend for live crawling updates.
*   **Geospatial Analysis**: Interactive global maps rendering media density and event hotspots.

### 3.3 Infrastructure
*   **Local Research Stack (Optional)**:
    *   **Database**: PostgreSQL (metadata, relational graph).
    *   **Queue/Cache**: Redis (deduplication and task scheduling).
*   **Zero-cost Publishing Baseline**:
    *   **Frontend**: GitHub Pages (static site).
    *   **Data**: build-time generated static JSON embedded into the frontend bundle.
    *   **Automation**: GitHub Actions for scheduled data refresh and Pages deployment.

---

## 4. Quick Start (Research Environment)

### Prerequisites
*   Python 3.11+
*   Node.js 18+
*   PostgreSQL & Redis

### Installation

**1. Backend (Intelligence Engine)**
```bash
cd backend
python -m venv venv
# Windows: venv\Scripts\activate | Mac/Linux: source venv/bin/activate
pip install -r requirements.txt
playwright install chromium  # Install headless browser
python main.py  # Starts API server on port 8002
```

**2. Frontend (Visualization Console)**
```bash
cd frontend
npm install
npm run dev
```

---

## 5. Deployment Status
*   **Live Dashboard**: [https://computational-social-science.github.io/globe-media-pulse/](https://computational-social-science.github.io/globe-media-pulse/)

---

## 6. License
**MIT License**
Copyright (c) 2026 Computational Social Science Lab.
