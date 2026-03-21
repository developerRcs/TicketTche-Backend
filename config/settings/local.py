# =============================================================================
# Settings — LOCAL DEVELOPMENT
# Uses PostgreSQL via Docker (docker-compose.yml)
# =============================================================================
from decouple import config

from .base import *  # noqa: F401, F403

DEBUG = True

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("DB_NAME", default="tickettche_local"),
        "USER": config("DB_USER", default="tickettche"),
        "PASSWORD": config("DB_PASSWORD", default="tickettche_local_pass"),
        "HOST": config("DB_HOST", default="db"),
        "PORT": config("DB_PORT", default="5432"),
        "OPTIONS": {
            "connect_timeout": 10,
        },
        "CONN_MAX_AGE": 60,
    }
}

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

# Redis via Docker
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": config("REDIS_URL", default="redis://redis:6379/0"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
        "TIMEOUT": 300,
    }
}

# Django Debug Toolbar (optional, install separately)
INTERNAL_IPS = ["127.0.0.1"]

# Looser password validation for local testing
AUTH_PASSWORD_VALIDATORS = []
