# =============================================================================
# Settings — PRODUÇÃO
# Uses PostgreSQL + Redis via Docker (docker-compose.prod.yml)
# =============================================================================
from decouple import Csv, config

from .base import *  # noqa: F401, F403

DEBUG = False

ALLOWED_HOSTS = config("ALLOWED_HOSTS", cast=Csv())

FRONTEND_URL = config("FRONTEND_URL", default="https://tickettche.com.br")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("DB_NAME"),
        "USER": config("DB_USER"),
        "PASSWORD": config("DB_PASSWORD"),
        "HOST": config("DB_HOST", default="db"),
        "PORT": config("DB_PORT", default="5432"),
        "OPTIONS": {
            "connect_timeout": 10,
            "sslmode": config("DB_SSLMODE", default="require"),
            # PostgreSQL-specific optimizations for low memory
            "options": "-c statement_timeout=30000",  # 30s max query time
        },
        "CONN_MAX_AGE": 600,  # Connection pooling (reuse connections)
        "CONN_HEALTH_CHECKS": True,  # Verify connections are healthy
    }
}

# Redis with password
REDIS_URL = config("REDIS_URL")

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SOCKET_CONNECT_TIMEOUT": 5,
            "SOCKET_TIMEOUT": 5,
            "RETRY_ON_TIMEOUT": True,
            "MAX_CONNECTIONS": 20,  # Reduced from 50 (limit connections for low RAM)
            "CONNECTION_POOL_KWARGS": {
                "max_connections": 20,
                "retry_on_timeout": True,
            },
        },
        "KEY_PREFIX": "tickettche",
        "TIMEOUT": 300,  # 5 minutes default
    }
}

# Session configuration (use cache, not database - saves RAM)
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"
SESSION_COOKIE_AGE = 3600  # 1 hour (shorter = less memory)

CELERY_BROKER_URL = config("CELERY_BROKER_URL")
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_TASK_ALWAYS_EAGER = False  # Run tasks async
CELERY_WORKER_CONCURRENCY = 1  # Only 1 worker (limited by 1GB RAM)
CELERY_WORKER_PREFETCH_MULTIPLIER = 1  # Don't prefetch tasks
CELERY_WORKER_MAX_TASKS_PER_CHILD = 100  # Restart worker after 100 tasks (prevent memory leaks)

# Email
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = config("EMAIL_HOST")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_USE_TLS = True
EMAIL_HOST_USER = config("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD")
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="noreply@tickettche.com")

# CORS
CORS_ALLOWED_ORIGINS = config("CORS_ALLOWED_ORIGINS", cast=Csv())

# Behind Nginx — trust X-Forwarded-Proto (HTTPS)
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Security — HTTPS redirect disabled until SSL cert is configured
SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = False  # MUST be False for double-submit CSRF pattern (frontend reads cookie)
CSRF_COOKIE_SAMESITE = "Lax"
X_FRAME_OPTIONS = "DENY"
REFERRER_POLICY = "strict-origin-when-cross-origin"

# Enforce payment webhook secret in production — system will fail to start without it
_mp_webhook_secret = config("MP_WEBHOOK_SECRET")
if not _mp_webhook_secret:
    raise RuntimeError("MP_WEBHOOK_SECRET must be set in production. Refusing to start.")
MP_WEBHOOK_SECRET = _mp_webhook_secret

# Logging
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "django.security": {"handlers": ["console"], "level": "ERROR", "propagate": False},
        "apps": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}
