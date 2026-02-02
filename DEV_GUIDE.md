# Globe Media Pulse Development Guide

This document covers local development/testing and the long-term free publishing path.

## 1. Modes

### 1.1 Static Frontend Mode (Default; zero-cost baseline)
- Runs the frontend only, with build-time generated static data embedded into the bundle.
- Backend/WebSocket/API are disabled by setting `VITE_STATIC_MODE=1`.
- Windows entrypoint: `start_dev.bat` (generates `frontend/src/lib/data.js`, then starts Vite).

### 1.2 Local Full-Stack Mode (Research)
- Runs frontend + backend + PostgreSQL + Redis + MinIO + Playwright locally via `docker-compose.yml`.
- Intended for crawling experiments, storage, and end-to-end validation.

## 2. Local Development (Full-Stack)

### Start
```bash
docker-compose up --build
```

### Services
- Frontend: http://localhost:5173
- Backend: http://localhost:8002 (Swagger UI: http://localhost:8002/docs)
- PostgreSQL: localhost:5433
- Redis: localhost:6380 (RedisInsight UI: http://localhost:8003)
- MinIO API: http://localhost:9002 (Console: http://localhost:9003)

### Stop
```bash
docker-compose down
```

Reset local data:
```bash
docker-compose down -v
```

## 3. Testing

Backend tests (inside container):
```bash
docker-compose exec backend pytest
```

Frontend checks (inside container):
```bash
docker-compose exec frontend npm run lint
docker-compose exec frontend npm run typecheck
```

## 4. Publishing (Long-term Free)

The supported publishing target is GitHub Pages, with GitHub Actions generating static data and deploying the site.

## 5. FAQ

**Q: Why does the frontend show offline / no live data?**  
A: Static mode disables API/WebSocket by design (`VITE_STATIC_MODE=1`). Use full-stack mode if you need live crawling.

**Q: How do I connect to the local database from my host machine?**  
A: `postgresql://postgres:password@localhost:5433/globemediapulse`
