# Development Environment Setup Guide

**Goal:** Setup a complete "Local + Remote" development environment in under 10 minutes.
**Cost:** $0 (Forever Free)

---

## 1. Prerequisites

- **Node.js**: v20+ (LTS recommended)
- **Python**: v3.11+
- **Docker Desktop**: Latest version
- **Git**: Latest version
- **VS Code** (Recommended)

---

## 2. Quick Start (Local)

### 2.1 Clone Repository
```bash
git clone https://github.com/YOUR_USERNAME/GlobeMediaPulse.git
cd GlobeMediaPulse
```

### 2.2 Frontend Setup
```bash
cd frontend
npm install
npm run dev
# Access at http://localhost:5173
```

### 2.3 Backend Setup (Docker)
```bash
# Root directory
cp .env.example .env # Create env file if needed
docker-compose up -d
# Crawler & Database will start.
# Logs: docker-compose logs -f
```

---

## 3. Local-to-Remote Tunneling (Cloudflare Tunnel)

To expose your local backend to the remote frontend (GitHub Pages) or external webhooks without deploying.

1.  **Install Cloudflared**: [Download Link](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/)
2.  **Login**:
    ```bash
    cloudflared tunnel login
    ```
3.  **Start Tunnel**:
    ```bash
    # Expose Frontend
    cloudflared tunnel --url http://localhost:5173
    
    # Expose Backend API (if running locally on 8000)
    cloudflared tunnel --url http://localhost:8000
    ```
4.  **Copy URL**: Use the generated `https://random-name.trycloudflare.com` as your API endpoint in the frontend config or share with teammates.

---

## 4. Deployment Pipeline

### 4.1 Frontend (GitHub Pages)
- **Trigger**: Push to `main` branch (changes in `frontend/`).
- **Action**: GitHub Action builds and deploys to `gh-pages` branch.
- **URL**: `https://YOUR_USERNAME.github.io/GlobeMediaPulse/`

### 4.2 Backend (Oracle Cloud Free Tier)
- **Trigger**: Push to `main` branch (changes in `backend/`).
- **Action**: GitHub Action SSHs into your Oracle Free Tier instance and runs `docker-compose up -d --build`.
- **Setup**:
    1.  Add secrets to GitHub Repo: `OCI_HOST`, `OCI_USER`, `OCI_SSH_KEY`.
    2.  Ensure Docker is installed on the remote server.

---

## 5. Troubleshooting

- **Frontend Connection Refused**: Ensure `npm run dev` is running and port 5173 is free.
- **Docker Permission Denied**: On Linux, add user to docker group: `sudo usermod -aG docker $USER`.
- **Cloudflare Tunnel Error**: Check internet connection and firewall settings.

---

## 6. Zero-Cost Architecture Verification

- **Frontend**: GitHub Pages (Free) + Cloudflare CDN (Free).
- **Backend**: Oracle Always Free (4 OCPU ARM, 24GB RAM).
- **Database**: Dockerized Postgres on Oracle Block Volume (Free).
- **SSL**: Cloudflare Universal SSL (Free).
