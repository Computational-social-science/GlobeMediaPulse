Write-Host "Starting Development Environment..." -ForegroundColor Green
docker compose -f docker-compose.yml --profile dev up --build
