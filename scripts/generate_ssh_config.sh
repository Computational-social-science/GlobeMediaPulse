#!/bin/bash

# Helper script to generate SSH config entry
# Usage: ./generate_ssh_config.sh <remote_host> <user> <key_path>

HOST=$1
USER=${2:-ubuntu}
KEY_PATH=${3:-~/.ssh/id_ed25519}

if [ -z "$HOST" ]; then
    echo "Usage: $0 <remote_host_ip> [user] [key_path]"
    exit 1
fi

echo "Generating SSH Config entry..."
echo ""
echo "Host gmp-remote"
echo "    HostName $HOST"
echo "    User $USER"
echo "    IdentityFile $KEY_PATH"
echo "    ForwardAgent yes"
echo "    LocalForward 8000 127.0.0.1:8000"
echo "    LocalForward 5173 127.0.0.1:5173"
echo ""
echo "👉 Copy the above block to your local ~/.ssh/config file."
