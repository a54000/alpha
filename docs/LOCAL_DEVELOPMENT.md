# Local Development

## Prerequisites

- Python 3.11+
- PostgreSQL 18+ (Homebrew install is supported)
- Virtual environment with project dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Database setup

The platform uses **PostgreSQL** as the primary runtime database. SQLite is reserved for unit tests only.

### 1. Create the database

If it does not already exist:

```bash
createdb -h /private/tmp -p 5433 nse_research_platform
```

Verify:

```bash
psql -h /private/tmp -p 5433 -l
```

### 2. Configure environment variables

Copy the example file and edit as needed:

```bash
cp .env.example .env
```

Example `DATABASE_URL` for the local Homebrew server:

```bash
DATABASE_URL=postgresql+psycopg2://surindersingh@localhost:5433/nse_research_platform
```

If `localhost` does not connect, use the Unix socket form from `.env.example`.

### 3. Run migrations

With `.env` in place:

```bash
alembic upgrade head
```

Rollback and re-apply:

```bash
alembic downgrade base
alembic upgrade head
```

### 4. Use the database in application code

```python
from db.session import build_session_factory

session_factory = build_session_factory()

with session_factory() as session:
    ...
```

`build_session_factory()` and `build_engine()` read `DATABASE_URL` automatically (including from `.env` via `python-dotenv`).

## Running tests

Tests use in-memory SQLite and do **not** require PostgreSQL or `DATABASE_URL`.

```bash
pytest
```

Migration tests use a temporary SQLite file and pass an explicit Alembic URL in test configuration.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `DATABASE_URL is not set` | Copy `.env.example` to `.env` |
| `connection refused` on port 5433 | Confirm PostgreSQL is running: `brew services list` |
| `database does not exist` | Run `createdb` (see above) |
| `role does not exist` | Update the username in `DATABASE_URL` |
