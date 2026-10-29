@echo off
REM One-command local start (Windows): Python env, database migrations, sample users, server.
cd /d "%~dp0"
if not exist backend\.venv ( python -m venv backend\.venv || goto :err )
backend\.venv\Scripts\python -m pip install -q -r backend\requirements.txt || goto :err
if not exist backend\.env (
  copy backend\.env.example backend\.env >nul
  echo Created backend\.env with the local PostgreSQL settings. Edit it if your database differs.
)
if not exist frontend\dist\index.html (
  where npm >nul 2>nul || ( echo frontend\dist is missing and Node.js is not installed. Install Node 18+ & goto :err )
  pushd frontend & call npm install && call npm run build & popd || goto :err
)
cd backend
.venv\Scripts\python manage.py migrate --noinput
if errorlevel 1 (
  echo.
  echo Could not prepare the database. Check backend\.env and that PostgreSQL is running.
  echo See README_POSTGRESQL.md - or set DB_ENGINE=sqlite in backend\.env for a quick start without PostgreSQL.
  goto :err
)
.venv\Scripts\python manage.py seed_users
echo Starting on http://127.0.0.1:8000  (Ctrl+C to stop)
.venv\Scripts\python manage.py runserver 127.0.0.1:8000 --noreload
goto :eof
:err
echo.
echo Setup failed - see the messages above.
pause
