import os
from datetime import timedelta
from pathlib import Path

from decouple import Csv, config

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = config("SECRET_KEY")

DEBUG = config("DEBUG", default=False, cast=bool)

ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1", cast=Csv())

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_filters",
    "django_celery_beat",
    "axes",  # Brute force protection & rate limiting
]

LOCAL_APPS = [
    "apps.core",
    "apps.accounts",
    "apps.companies",
    "apps.events",
    "apps.tickets",
    "apps.orders",
    "apps.audit",
    "apps.payments",
    "apps.withdrawals",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "axes.middleware.AxesMiddleware",  # MUST be after AuthenticationMiddleware
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.audit.middleware.AuditRequestMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

AUTH_USER_MODEL = "accounts.CustomUser"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = config("STATIC_ROOT", default=str(BASE_DIR / "staticfiles"))

MEDIA_URL = "/media/"
MEDIA_ROOT = config("MEDIA_ROOT", default=str(BASE_DIR / "media"))

# ── Cloudflare R2 (storage de mídia) ─────────────────────────────────────────
# Quando R2_BUCKET_NAME está definido, usa R2. Caso contrário, usa disco local.
R2_ACCOUNT_ID        = config("R2_ACCOUNT_ID", default="")
R2_ACCESS_KEY_ID     = config("R2_ACCESS_KEY_ID", default="")
R2_SECRET_ACCESS_KEY = config("R2_SECRET_ACCESS_KEY", default="")
R2_BUCKET_NAME       = config("R2_BUCKET_NAME", default="")
R2_PUBLIC_URL        = config("R2_PUBLIC_URL", default="")  # ex: https://assets.seudominio.com.br

# Django 4.2+ usa STORAGES em vez de DEFAULT_FILE_STORAGE/STATICFILES_STORAGE
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
}

if R2_BUCKET_NAME:
    STORAGES["default"]["BACKEND"] = "apps.core.r2_storage.R2MediaStorage"
    MEDIA_URL = R2_PUBLIC_URL.rstrip("/") + "/"

    AWS_ACCESS_KEY_ID       = R2_ACCESS_KEY_ID
    AWS_SECRET_ACCESS_KEY   = R2_SECRET_ACCESS_KEY
    AWS_STORAGE_BUCKET_NAME = R2_BUCKET_NAME
    AWS_S3_ENDPOINT_URL     = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
    AWS_S3_REGION_NAME      = "auto"
    AWS_S3_SIGNATURE_VERSION = "s3v4"
    AWS_S3_FILE_OVERWRITE   = False
    AWS_DEFAULT_ACL         = None
    AWS_QUERYSTRING_AUTH    = False  # URLs públicas sem expiração
    AWS_S3_CUSTOM_DOMAIN    = R2_PUBLIC_URL.replace("https://", "").replace("http://", "").rstrip("/") if R2_PUBLIC_URL else None

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.StandardPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "EXCEPTION_HANDLER": "apps.core.exceptions.custom_exception_handler",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

CORS_ALLOWED_ORIGINS = config("CORS_ALLOWED_ORIGINS", default="http://localhost:3000", cast=Csv())
CORS_ALLOW_CREDENTIALS = True

CELERY_BROKER_URL = config("CELERY_BROKER_URL", default="redis://localhost:6379/1")
CELERY_RESULT_BACKEND = config("REDIS_URL", default="redis://localhost:6379/0")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "UTC"

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": config("REDIS_URL", default="redis://localhost:6379/0"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    }
}

# MercadoPago Checkout Transparente (Orders API)
MP_ACCESS_TOKEN = config("MP_ACCESS_TOKEN", default="TEST-access-token")
MP_PUBLIC_KEY = config("MP_PUBLIC_KEY", default="TEST-public-key")
MP_WEBHOOK_SECRET = config("MP_WEBHOOK_SECRET", default="")
MP_USER_ID = config("MP_USER_ID", default="")

PAYMENT_GATEWAY_CLASS = config(
    "PAYMENT_GATEWAY_CLASS",
    default="apps.payments.providers.mercadopago_provider.MercadoPagoGateway",
)

# QR code signing — dedicated key, never reuse SECRET_KEY for domain-specific HMACs
QR_SIGNING_KEY = config("QR_SIGNING_KEY", default="dev-qr-signing-key-CHANGE-IN-PRODUCTION")

# Social login audience validation
GOOGLE_CLIENT_ID = config("GOOGLE_CLIENT_ID", default="")
FACEBOOK_APP_ID = config("FACEBOOK_APP_ID", default="")
FACEBOOK_APP_SECRET = config("FACEBOOK_APP_SECRET", default="")

# ============================================================
# HTTP Security Headers (active in production via env vars)
# ============================================================
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
REFERRER_POLICY = "strict-origin-when-cross-origin"

# These activate only when HTTPS=True is set in the environment
HTTPS = config("HTTPS", default=False, cast=bool)
if HTTPS:
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000          # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# ============================================================
# django-axes: Brute Force Protection & Rate Limiting
# ============================================================
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",  # MUST be first for axes to work
    "django.contrib.auth.backends.ModelBackend",
]

# Axes configuration
AXES_ENABLED = True
AXES_FAILURE_LIMIT = 5  # Block after 5 failed login attempts
AXES_COOLOFF_TIME = timedelta(minutes=30)  # Block for 30 minutes
AXES_RESET_ON_SUCCESS = True  # Reset failure count on successful login
AXES_LOCKOUT_TEMPLATE = None  # Return 403 JSON instead of HTML template
AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"]]  # Track by username + IP (recommended over deprecated setting)
AXES_IPWARE_PROXY_COUNT = 1  # Trust 1 proxy (Nginx)
AXES_IPWARE_META_PRECEDENCE_ORDER = [
    "HTTP_X_FORWARDED_FOR",  # Behind reverse proxy
    "REMOTE_ADDR",
]
