# PostgreSQL with the Django backend — local setup and Render connection

Django reads the database settings from **environment variables**, so no password is ever written in source code:
`DB_ENGINE`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DB_SSLMODE`.

| | Local development | Render production |
| --- | --- | --- |
| Where the values live | `backend/.env` (git-ignored) | Render environment variables (filled from the database by `render.yaml`) |
| Settings module | `config.settings.local` | `config.settings.production` |
| `DB_HOST` | `localhost` | the Render database's internal host (`dpg-…`) — **not `localhost`** (production refuses to start) |
| SSL | optional | `require` |

Equivalent of your original Django block, now driven by variables:
```python
DATABASES = {"default": {"ENGINE": "django.db.backends.postgresql", "NAME": env("DB_NAME"), "USER": env("DB_USER"),
                         "PASSWORD": env("DB_PASSWORD"), "HOST": env("DB_HOST"), "PORT": env("DB_PORT")}}   # backend/config/settings/base.py
```

> Tested: the full test suite (66 tests), `migrate`, user seeding, and an end-to-end run with gunicorn on **production settings** all passed against a real PostgreSQL (unix-socket connection). A TCP + SSL connection to Render PostgreSQL was **not** tested here.

---

## 1. Install PostgreSQL (local)
Download PostgreSQL 14+ from https://www.postgresql.org/download/ (Windows/macOS) or `sudo apt install postgresql` (Ubuntu). Keep port **5432** and remember the `postgres` admin password.

## 2. Create the local database and user
Open `psql` as the admin (Windows: *SQL Shell (psql)*; Linux: `sudo -u postgres psql`) and run:
```sql
CREATE USER myapp_user WITH PASSWORD 'MyApp@123';
CREATE DATABASE myapp_db OWNER myapp_user;
\c myapp_db
GRANT ALL ON SCHEMA public TO myapp_user;
\q
```
`MyApp@123` is the **local-development-only** password from your initial setup. Never reuse it in production.

## 3. Local `backend/.env`
`run.bat` / `run.sh` copy `backend/.env.example` to `backend/.env` for you. It contains:
```ini
DB_ENGINE=postgres
DB_NAME=myapp_db
DB_USER=myapp_user
DB_PASSWORD=MyApp@123
DB_HOST=localhost
DB_PORT=5432
```
(Special characters in the password need no URL-encoding here, because these are separate settings, not a URL.)

## 4. Create the tables and the first users
```bash
cd backend
python manage.py migrate         # Django migrations create all tables
python manage.py seed_users      # admin (Admin@123), md01 (Md@123), user01..user10 (User@123); on an existing DB add --reset
python manage.py runserver 127.0.0.1:8000
```
Check: `psql -h localhost -U myapp_user -d myapp_db -c "\dt"` lists `portal_user`, `portal_document`, `portal_auditlog`, `django_session`, `django_migrations`, … and http://127.0.0.1:8000/api/health returns `{"status":"ok"}` (it runs `SELECT 1` against the database).

---

## 5. Render PostgreSQL (production)
The blueprint (`render.yaml`) creates the database and wires `DB_*` into the web service; see `docs/RENDER_DEPLOYMENT.md`. Summary:

1. Deploy the blueprint: it creates the `ea-db` database (user `ea_app`) and sets these on the web service (nothing goes into source code):
   ```
   DJANGO_SETTINGS_MODULE=config.settings.production
   DB_NAME / DB_USER / DB_PASSWORD / DB_HOST / DB_PORT  (filled from the database)   DB_SSLMODE=require
   ```
2. Use the database's *internal* host name (same region as the web service); `DB_HOST` may not be `localhost`.
3. To use an existing PostgreSQL instead, delete the `databases:` block in `render.yaml` and enter the `DB_*` values in the dashboard.
4. Passwords live only in Render's environment variables; rotate them there.
5. Deploy. `startup.sh` runs `python manage.py migrate` on every start, so the schema is created/updated automatically. Create the first admin once: `python manage.py create_admin …` (Render Shell).

## 6. Backup
```bash
pg_dump -h localhost -U myapp_user -d myapp_db -F c -f backup.dump
pg_restore -h localhost -U myapp_user -d myapp_db --clean --if-exists backup.dump
```
Render: managed database backups (per plan) and disk snapshots, see `docs/OPERATIONS.md`. Back up the uploaded-files folder/Blob container together with the database.

## 7. Troubleshooting
| Error | Cause → fix |
| --- | --- |
| `connection refused` / `could not connect to server` | PostgreSQL not running, or wrong `DB_HOST`/`DB_PORT` |
| `password authentication failed for user` | wrong `DB_PASSWORD` in `backend/.env` (or the Render environment variable) |
| `database "myapp_db" does not exist` | run the `CREATE DATABASE` from step 2 |
| `permission denied for schema public` | `GRANT ALL ON SCHEMA public TO <user>;` while connected to the database (needed on PostgreSQL 15+) |
| `ImproperlyConfigured: DB_HOST must be the PostgreSQL server host name … not localhost` | production settings need the real server name |
| `SSL connection is required` / `no pg_hba.conf entry` | `DB_SSLMODE=require` (default in production) |
| Timeout from the web service | use the database's *internal* host name, in the same region |
| Local run without PostgreSQL | `DB_ENGINE=sqlite` in `backend/.env` |
