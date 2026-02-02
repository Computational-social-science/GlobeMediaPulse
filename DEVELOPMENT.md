# Development Guide

## Environment Modes

### 1. Static Frontend Mode (Default)
**"Zero-cost, long-term free publishing"**
- **Frontend**: Runs locally (`localhost:5173`) or on GitHub Pages.
- **Backend**: Disabled.
- **Data**: Loaded from build-time generated static bundle (`frontend/src/lib/data.js`).
- **Usage (Windows)**: Run `start_dev.bat` in the project root.

### 2. Local Full-Stack Mode (Research)
**"Local frontend + local backend + local data stores"**
- **Usage**: `docker-compose up --build`
- **Frontend API (optional)**:
  - `VITE_API_URL=http://localhost:8002`
  - `VITE_WS_URL=ws://localhost:8002`

## Guardrails (TRAE / Portability / Cost)
- Do not hardcode remote endpoints; require explicit environment variables.
- Use relative paths in code and docs to keep the workspace portable.
- Default architecture must remain free-to-run with GitHub Pages + GitHub Actions.

## Workflow
1. **Edit Code**: Modify Svelte components in `frontend/src`.
2. **Preview**: Changes reflect immediately in the local browser.
3. **Publish**: `git push` to trigger GitHub Pages deployment.
