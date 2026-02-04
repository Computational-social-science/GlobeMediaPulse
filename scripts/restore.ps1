param(
    [switch]$WithFrontend
)

$profileArgs = @()
if ($WithFrontend) {
    $profileArgs = @("--profile", "dev")
}

docker compose -f docker-compose.yml down -v --remove-orphans
docker system prune -f
docker compose -f docker-compose.yml @profileArgs up -d --build --force-recreate
