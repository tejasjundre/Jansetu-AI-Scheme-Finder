"""
WSGI config for ai_sakhi project.

This file exposes the WSGI callable as a module-level variable named ``application``.

It is used by WSGI-compatible web servers to serve your project.
"""

import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_sakhi.settings')

application = get_wsgi_application()
