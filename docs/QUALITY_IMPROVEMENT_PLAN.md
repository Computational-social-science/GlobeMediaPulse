# Quality Improvement & Prevention Plan

## 1. Sidebar Standardization
**Problem**: Inconsistent sidebar designs and code duplication led to visual chaos and maintenance overhead.
**Solution**: 
- Created reusable `src/lib/components/Sidebar.svelte`.
- Enforced usage in `App.svelte`.
- **Policy**: All pages requiring a sidebar MUST use the `Sidebar` component. Hardcoded `<aside>` elements are PROHIBITED.
**Checklist**:
- [ ] Verify `Sidebar` component usage in all layouts.
- [ ] Ensure no direct CSS overrides on sidebar classes unless strictly necessary.

## 2. Code Quality Gates (Zero Regression)
**Problem**: Lint errors (e.g., missing arguments) and style violations slipped into production.
**Solution**:
- **Pre-commit Hooks**: Added `.pre-commit-config.yaml` checking whitespace, YAML syntax, Black formatting, and Isort.
- **CI Pipeline**: Existing CI runs tests; recommend adding `pre-commit run --all-files` to CI.
**Policy**:
- Developers MUST install pre-commit hooks: `pip install pre-commit && pre-commit install`.
- CI MUST fail if linting or tests fail.

## 3. Crawler Stability
**Problem**: 
- `time.sleep(30)` in middleware blocked the async reactor, causing timeouts.
- Parsing failures caused crashes.
**Solution**:
- **Non-blocking Retry**: Replaced `time.sleep` with Scrapy's built-in retry/backoff mechanisms.
- **Robust Parsing**: Added try-except blocks around `trafilatura` extraction.
- **Testing**: Added `backend/tests/test_crawler_stability.py` covering middleware and parsing logic.
**Metric Target**: Crawler error rate < 0.1%.

## 4. Configuration Safety (API Keys)
**Problem**: `CRITICAL CONFIG ERROR` loop when `MEDIA_CLOUD_API_KEY` was missing.
**Solution**:
- **Robust Settings**: Modified `settings.py` to load `.env` automatically and WARN instead of CRASH if key is missing.
- **Graceful Degradation**: System proceeds with limited functionality if keys are absent.
**Policy**:
- Never use `sys.exit()` for missing optional configuration. Use warnings.
- Always use `pydantic-settings` or `dotenv` for environment loading.

## 5. Implementation Plan
1.  **Immediate**:
    *   [x] Standardize `App.svelte` sidebar.
    *   [x] Fix `settings.py` config loading.
    *   [x] Fix Crawler middleware and parsing.
    *   [x] Add Unit Tests.
    *   [x] Create `.pre-commit-config.yaml`.
2.  **Next Steps**:
    *   Run `pre-commit run --all-files` to format existing codebase.
    *   Monitor Crawler error rates in production.
