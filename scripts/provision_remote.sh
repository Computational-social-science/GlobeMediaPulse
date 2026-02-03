#!/bin/bash

# ==============================================================================
# Automated Server Provisioning Script (Zero-Cost Deployment)
# Target: Ubuntu 22.04 LTS (Oracle Cloud Ampere / AWS Free Tier)
# ==============================================================================

set -e # Exit immediately if a command exits with a non-zero status.

# 1. System Update & Dependencies
echo "[1/5] Updating system packages..."
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    git \
    ufw

# 2. Install Docker Engine & Docker Compose
echo "[2/5] Installing Docker..."
if ! command -v docker &> /dev/null; then
    sudo mkdir -p /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
      $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    sudo apt-get update
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
    
    # Enable non-root docker execution
    sudo usermod -aG docker $USER
    echo "Docker installed successfully."
else
    echo "Docker already installed."
fi

# 3. Security Hardening (UFW)
echo "[3/5] Configuring Firewall..."
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp  # SSH
sudo ufw allow 80/tcp  # HTTP
sudo ufw allow 443/tcp # HTTPS
# sudo ufw enable # Commented out to prevent accidental lockout; enable manually after verifying SSH

# 4. Project Setup
echo "[4/5] Setting up project directory..."
PROJECT_DIR="/home/$USER/GlobeMediaPulse"
mkdir -p "$PROJECT_DIR/data/crawler_persistence"
mkdir -p "$PROJECT_DIR/data/logs"
mkdir -p "$PROJECT_DIR/data/output"

# 5. Log Rotation Configuration (Docker)
echo "[5/5] Configuring Docker Log Rotation..."
# This is usually handled in daemon.json or docker-compose, but we ensure the daemon is configured
if [ ! -f /etc/docker/daemon.json ]; then
    echo '{
      "log-driver": "json-file",
      "log-opts": {
        "max-size": "10m",
        "max-file": "3"
      }
    }' | sudo tee /etc/docker/daemon.json
    sudo systemctl restart docker
fi

echo "✅ Server Provisioning Complete!"
echo "Next Steps:"
echo "1. Logout and Login to apply Docker group changes."
echo "2. Add your SSH public key to GitHub Deploy Keys."
echo "3. Run deployment via GitHub Actions."
