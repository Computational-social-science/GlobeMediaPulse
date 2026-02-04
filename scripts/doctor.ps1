$ErrorActionPreference = "Stop"

Write-Host "docker system info" -ForegroundColor Cyan
docker system info

Write-Host "docker ps -a" -ForegroundColor Cyan
docker ps -a

Write-Host "docker compose ps" -ForegroundColor Cyan
docker compose -f docker-compose.yml ps

Write-Host "docker compose logs (tail=200)" -ForegroundColor Cyan
docker compose -f docker-compose.yml logs --tail=200

python scripts/health_check.py
