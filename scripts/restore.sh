#!/bin/sh
set -e

WITH_FRONTEND="${WITH_FRONTEND:-0}"
PROFILE_ARGS=""
if [ "$WITH_FRONTEND" = "1" ] || [ "$WITH_FRONTEND" = "true" ]; then
  PROFILE_ARGS="--profile dev"
fi

docker compose -f docker-compose.yml down -v --remove-orphans
docker system prune -f
docker compose -f docker-compose.yml $PROFILE_ARGS up -d --build --force-recreate
