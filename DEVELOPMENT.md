# Development Guide

## Environment Modes

### 1. Hybrid Mode (Recommended)
**"Local Frontend, Cloud Backend"**
- **Frontend**: Runs locally on your machine (`localhost:5173`).
- **Backend**: Connects to the live Fly.io instance (`globe-media-pulse.fly.dev`).
- **Data**: Real production data (Media Seeds, Articles).
- **Usage**: Run `start_dev.bat` in the project root.

### 2. Full Remote Mode
**"Cloud Frontend, Cloud Backend"**
- **Frontend**: Accessed via GitHub Pages (e.g., `https://computational-social-science.github.io/globe-media-pulse/`).
- **Backend**: Runs on Fly.io.
- **Usage**: Push changes to `main` branch. GitHub Actions will auto-deploy.

## Key Configurations
- **Frontend Config**: `frontend/.env.local`
  ```properties
  VITE_API_URL=https://globe-media-pulse.fly.dev
  VITE_WS_URL=wss://globe-media-pulse.fly.dev
  ```
- **Backend CORS**: `backend/main.py`
  - Allowed Origins: `localhost:5173`, `localhost:3000`, GitHub Pages domain.

## Workflow
1. **Edit Code**: Modify Svelte components in `frontend/src`.
2. **Preview**: Changes reflect immediately in the local browser.
3. **Commit**: `git push` to trigger deployment.
