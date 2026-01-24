# Globe Media Pulse: Global Spelling Error Fingerprints in English News (2016–Present)
**Globe Media Pulse: 基于全球英文新闻的人类拼写错误行为指纹研究**

Target Journal: *Nature Human Behaviour*

## Overview
This project investigates spelling errors in global English news (2016–Present) as emergent behavioural traces of national news production systems. By analyzing the statistical structure of spelling errors across 195+ countries, we aim to identify stable, comparable, and evolving "fingerprints" of human behaviour.

## Architecture
The project follows a Monorepo structure:

- **`/backend`**: Python 3.11+ research engine (FastAPI, spaCy, rapidfuzz, scikit-learn). Handles data crawling, error detection, vectorization, and statistical analysis.
- **`/frontend`**: Svelte + Vite + TypeScript interactive visualization. Provides exploratory data analysis (EDA) tools, global maps, and fingerprint radar charts.

## Setup

### Prerequisites
- Python 3.11+
- Node.js 18+

### Installation

1.  **Backend**
    ```bash
    cd backend
    python -m venv venv
    source venv/bin/activate  # or venv\Scripts\activate on Windows
    pip install -r requirements.txt
    ```

2.  **Frontend**
    ```bash
    cd frontend
    npm install
    npm run dev
    ```

## Research Plan
See [News.md](News.md) for the detailed research proposal and engineering task breakdown.

## License
MIT
