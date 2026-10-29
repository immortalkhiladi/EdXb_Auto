#!/usr/bin/env bash
# Render start command:  bash backend/startup.sh   (see render.yaml)
# Applies database migrations, then starts the Django app with gunicorn. No Docker.
set -e
cd "$(dirname "$0")"
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings.production}"
python manage.py migrate --noinput
# glibc creates one malloc arena per thread; capping them keeps worker RSS from creeping up under gthread workers
export MALLOC_ARENA_MAX="${MALLOC_ARENA_MAX:-2}"
# threaded workers: one slow upload/download no longer blocks every other request on that worker.
# --max-requests recycles each worker periodically (caps slow memory growth on the 512 MB instance);
# /dev/shm keeps the worker heartbeat off the (possibly slow) disk.
exec gunicorn config.wsgi:application --bind "0.0.0.0:${PORT:-10000}" \
     --workers "${WEB_CONCURRENCY:-2}" --worker-class gthread --threads "${GUNICORN_THREADS:-4}" \
     --timeout 120 --graceful-timeout 30 --keep-alive 5 \
     --max-requests "${GUNICORN_MAX_REQUESTS:-10000}" --max-requests-jitter 200 \
     $( [ -d /dev/shm ] && [ -w /dev/shm ] && echo "--worker-tmp-dir /dev/shm" ) --access-logfile - --error-logfile -
