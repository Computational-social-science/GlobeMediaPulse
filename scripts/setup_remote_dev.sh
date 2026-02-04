#!/bin/bash
set -e

# ==============================================================================
# Remote Development Environment Setup Script
# Target: Ubuntu 22.04 LTS / Debian 11+
# Usage: ./setup_remote_dev.sh
# ==============================================================================

echo "🚀 Initializing Remote Development Environment..."

# 1. Update System
echo "[1/6] Updating system packages..."
sudo apt-get update && sudo apt-get upgrade -y

# 2. Install Essential Tools
echo "[2/6] Installing essential tools (curl, git, build-essential)..."
sudo apt-get install -y curl git build-essential unzip htop net-tools

# 3. Install Docker Engine & Docker Compose
if ! command -v docker &> /dev/null; then
    echo "[3/6] Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    echo "⚠️  User added to docker group. You may need to re-login."
else
    echo "[3/6] Docker already installed."
fi

# 4. Install Node.js (for Frontend)
if ! command -v node &> /dev/null; then
    echo "[4/6] Installing Node.js 20.x..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    sudo apt-get install -y nodejs
else
    echo "[4/6] Node.js already installed."
fi

# 5. Install Python 3.11 (if not default)
echo "[5/6] Checking Python version..."
python3 --version

# 6. Firewall Configuration (UFW)
echo "[6/6] Configuring Firewall (UFW)..."
# Allow SSH
sudo ufw allow 22/tcp
# Allow Application Ports
sudo ufw allow 8000/tcp  # Backend API
sudo ufw allow 5173/tcp  # Frontend Dev
sudo ufw allow 5432/tcp  # Postgres (Optional, use tunnel preferred)
sudo ufw allow 6379/tcp  # Redis (Optional)

echo "✅ Remote Environment Setup Complete!"
echo "👉 Next Steps:"
echo "1. Clone repository: git clone <repo_url>"
echo "2. Add your public SSH key to ~/.ssh/authorized_keys"
echo "3. Connect via VS Code Remote - SSH"
