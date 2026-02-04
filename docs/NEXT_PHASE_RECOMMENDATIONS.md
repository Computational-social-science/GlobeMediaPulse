# Next Phase Recommendations

**Date:** 2026-02-03

---

## 1. Technical Architecture
### 1.1 Self-Healing Mechanism
- **Observation:** `sentinel.py` is a good start but relies on CLI parsing which is brittle across OS versions.
- **Recommendation:** Migrate to using the Docker SDK for Python (`pip install docker`) for robust container management.

### 1.2 Frontend Performance
- **Observation:** Large GeoJSON files cause map lag.
- **Recommendation:** Implement vector tiles (MVT) or server-side clustering for map data.

## 2. Process & Workflow
### 2.1 Code Quality
- **Observation:** ESLint fixes most style issues, but logic errors persist.
- **Recommendation:** Introduce SonarQube for deeper static analysis.

### 2.2 Research Collaboration
- **Recommendation:** Establish a weekly "Data Review" meeting to validate crawler output against research hypotheses.

## 3. Security
- **Recommendation:** Although Auth was removed for the MVP, re-introducing a simple Basic Auth (Nginx level) is recommended if exposing to the public internet.
