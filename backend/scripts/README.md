# Database Migrations

Currently, Globe Media Pulse uses a lightweight **auto-initialization** approach, and also includes Alembic scaffolding for future versioned migrations.

## Current Workflow
- The application can initialize required tables on startup if they do not exist.
- Alembic is present under `backend/alembic/`, but migrations are not yet a strict requirement for every schema change.

## Manual Migrations
If you need to manually alter the schema:
1. Connect to the database:
   ```bash
   docker-compose exec db psql -U postgres -d globemediapulse
   ```
2. Run SQL commands.

## Future Improvements
- Integrate **Alembic** for versioned migrations.
- Place `.sql` or python migration scripts in this folder.
