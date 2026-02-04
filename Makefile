COMPOSE=docker compose -f docker-compose.yml

up:
	$(COMPOSE) up -d --build

up-dev:
	$(COMPOSE) --profile dev up -d --build

ps:
	$(COMPOSE) ps

logs:
	$(COMPOSE) logs -f --tail=200

down:
	$(COMPOSE) down --remove-orphans

down-v:
	$(COMPOSE) down -v --remove-orphans

restore:
	$(COMPOSE) down -v --remove-orphans
	docker system prune -f
	$(COMPOSE) up -d --build --force-recreate

doctor:
	python scripts/health_check.py

