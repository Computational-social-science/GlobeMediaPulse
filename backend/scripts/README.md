# Database Migrations

Currently, Globe Media Pulse uses a **Schema-on-Read** or **Auto-Initialization** approach via `backend/storage.py`.

## Current Workflow
- The application automatically initializes necessary tables (`error_events`, etc.) in `storage.py` on startup if they do not exist.
- No formal migration tool (like Alembic) is currently enforced, but may be added as the schema complexity grows.

## Manual Migrations
If you need to manually alter the schema:
1. Connect to the database:
   ```bash
   fly pg connect -a globemediapulse-db-production
   ```
2. Run SQL commands.

## Future Improvements
- Integrate **Alembic** for versioned migrations.
- Place `.sql` or python migration scripts in this folder.
