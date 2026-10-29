import os

from django.core.wsgi import get_wsgi_application

# Production entry point (gunicorn). Settings come from the environment (Render environment variables).
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")
application = get_wsgi_application()
