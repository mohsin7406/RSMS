# Repair Shop Management System

RSMS is a Flask-based repair shop management system for customers, repair orders, workflow tracking and future repair-shop automation.

## Current stack

- Python 3.12+
- Flask
- Flask-SQLAlchemy
- Flask-Migrate / Alembic
- PostgreSQL in production
- Gunicorn
- TailwindCSS / Alpine.js frontend
- Flask-Limiter for rate limiting

## Production security baseline

- Production requires `SECRET_KEY`, `DATABASE_URL` and shared `RATELIMIT_STORAGE_URI`.
- Session cookies are HTTP-only, SameSite=Lax and Secure by default in production.
- State-changing requests require a CSRF token.
- Login is rate limited.
- Public self-registration is disabled; administrators create staff accounts.
- Role-based authorization is enforced on sensitive operations.
- Demo database seeding is disabled unless explicitly enabled.
- Local SQLite databases are excluded from source control.
- Database migrations are version controlled.
- Security response headers are enabled.

## Local development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
export FLASK_ENV=development
python run.py
```

Development can use SQLite and in-memory rate limiting.

## Production configuration

Set the following environment variables using your deployment secret manager or service configuration. Do not commit `.env` files or passwords.

```text
FLASK_ENV=production
SECRET_KEY=<long-random-secret>
DATABASE_URL=postgresql+psycopg://rsms:<password>@127.0.0.1:5432/rsms
RATELIMIT_STORAGE_URI=redis://127.0.0.1:6379/1
SESSION_COOKIE_SECURE=true
```

Run database migrations before starting the application:

```bash
flask --app run.py db upgrade
```

Create the first administrator with environment variables `ADMIN_EMAIL` and `ADMIN_PASSWORD` and then run:

```bash
flask --app run.py create-admin
```

Start the production server behind Nginx or another TLS-terminating reverse proxy:

```bash
gunicorn --config gunicorn.conf.py run:app
```

## Testing

```bash
pytest -q
```

CI runs the test suite on pushes to the main and production-hardening branches and on pull requests targeting main.

## Important

Do not run demo seed commands against a production database. `seed-db` and `seed-db-all` require `ALLOW_DEMO_SEED=true` explicitly.
