# 运行后端测试
Write-Host "Running Backend Tests..." -ForegroundColor Green
docker-compose exec backend pytest
