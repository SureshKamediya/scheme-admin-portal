"""
WSGI config for Reyasat_LIG_EWS_backend project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os
import sys

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Reyasat_LIG_EWS_backend.settings')

# This will show up in journalctl logs.
print(f"Gunicorn-loaded SECRET_KEY: '{os.environ.get('SECRET_KEY')}'", file=sys.stderr)

application = get_wsgi_application()
