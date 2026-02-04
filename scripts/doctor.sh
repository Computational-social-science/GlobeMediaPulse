#!/bin/sh
set -e

echo "docker system info"
docker system info

echo "docker ps -a"
docker ps -a

echo "docker compose ps"
docker compose -f docker-compose.yml ps

echo "docker compose logs (tail=200)"
docker compose -f docker-compose.yml logs --tail=200

python scripts/health_check.py
