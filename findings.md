# Findings & Technical Decisions

## 1. Pydantic V1 Compatibility with Python 3.14
**Issue:** `pydantic.v1` fails to infer types from annotations in Python 3.14 (Preview), causing `ConfigError: unable to infer type for attribute "X"` in libraries like `spacy`.
**Root Cause:** Python 3.14 likely changes how `__annotations__` or `typing` introspection works, and `pydantic` V1 (legacy) relies on older behavior.
**Solution:** Patched `venv\Lib\site-packages\pydantic\v1\fields.py` to fallback to `Any` when type inference fails (`self.type_ is Undefined`).
**Impact:** Fixes `spacy`, `weasel`, and other libraries relying on Pydantic V1 without requiring manual modification of every schema file.

## 2. Distributed Crawler Stabilization
**Issue:** Crawler was blocked by Spacy import errors.
**Resolution:** With the Pydantic patch, Spacy loads correctly. `scrapy list` confirms `universal_news_spider` is available.
**Verification:** `manage.py crawl` command added to launch spiders easily.

## 3. Docker Environment
**Optimization:** Created `Dockerfile.dev` for backend/frontend to support hot-reloading and better caching.
**Orchestration:** `docker-compose.yml` updated to use these dev images.
