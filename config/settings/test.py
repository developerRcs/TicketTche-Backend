# =============================================================================
# Settings — TEST (SQLite in-memory for fast, portable testing)
# =============================================================================
from .base import *  # noqa: F401, F403

DEBUG = True

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Cache em memória nos testes (mais rápido, sem side-effects)
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
]

# Desabilita celery nos testes (tasks executam sincronamente)
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# QR codes vão para diretório temporário
MEDIA_ROOT = "/tmp/tickettche_test_media"
STATIC_ROOT = "/tmp/tickettche_test_static"

# Emails não são enviados nos testes
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Senha fraca permitida nos testes
AUTH_PASSWORD_VALIDATORS = []

# Logs silenciados nos testes
LOGGING = {}

# Faster password hashing for tests
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# Disable throttling in tests
REST_FRAMEWORK = {
    **REST_FRAMEWORK,  # noqa: F405
    "DEFAULT_THROTTLE_CLASSES": [],
    "DEFAULT_THROTTLE_RATES": {},
}
