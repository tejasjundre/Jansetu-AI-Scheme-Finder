import importlib.util
import os
import sys
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional local helper
    load_dotenv = None


BASE_DIR = Path(__file__).resolve().parent.parent
RUNNING_TESTS = "test" in sys.argv
RUNNING_DEV_SERVER = "runserver" in sys.argv

if load_dotenv:
    load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_int(name, default=0):
    try:
        return int(str(os.getenv(name, default)).strip())
    except (TypeError, ValueError):
        return default


def env_list(name, default=""):
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


def package_available(module_name):
    return importlib.util.find_spec(module_name) is not None


def parse_database_url(database_url):
    parsed = urlparse(database_url)
    scheme = parsed.scheme.lower()

    if scheme in {"postgres", "postgresql", "pgsql", "psql"}:
        engine = "django.db.backends.postgresql"
    elif scheme in {"mysql"}:
        engine = "django.db.backends.mysql"
    elif scheme in {"sqlite", "sqlite3"}:
        engine = "django.db.backends.sqlite3"
    else:
        raise ValueError(f"Unsupported database scheme: {scheme}")

    if engine == "django.db.backends.sqlite3":
        raw_path = parsed.path.replace("/", "", 1) or "db.sqlite3"
        db_path = raw_path if os.path.isabs(raw_path) else str(BASE_DIR / raw_path)
        return {
            "ENGINE": engine,
            "NAME": db_path,
            "CONN_MAX_AGE": 0,
        }

    options = {}
    query_params = parse_qs(parsed.query)
    ssl_mode = query_params.get("sslmode", [None])[0]
    if ssl_mode:
        options["sslmode"] = ssl_mode

    config = {
        "ENGINE": engine,
        "NAME": unquote((parsed.path or "").replace("/", "", 1)),
        "USER": unquote(parsed.username or ""),
        "PASSWORD": unquote(parsed.password or ""),
        "HOST": parsed.hostname or "localhost",
        "PORT": str(parsed.port or "5432"),
        "CONN_MAX_AGE": env_int("DB_CONN_MAX_AGE", 60),
    }
    if options:
        config["OPTIONS"] = options
    return config


def build_database_config():
    database_url = os.getenv("DATABASE_URL", "").strip()
    if database_url:
        try:
            return parse_database_url(database_url)
        except ValueError:
            pass

    if os.getenv("DB_ENGINE"):
        engine = os.getenv("DB_ENGINE", "django.db.backends.postgresql").strip()
        config = {
            "ENGINE": engine,
            "NAME": os.getenv("DB_NAME", ""),
            "USER": os.getenv("DB_USER", ""),
            "PASSWORD": os.getenv("DB_PASSWORD", ""),
            "HOST": os.getenv("DB_HOST", "localhost"),
            "PORT": os.getenv("DB_PORT", "5432"),
            "CONN_MAX_AGE": env_int("DB_CONN_MAX_AGE", 60),
        }
        if engine == "django.db.backends.sqlite3":
            config["NAME"] = str(BASE_DIR / "db.sqlite3")
            config["CONN_MAX_AGE"] = 0
        return config

    return {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
        "CONN_MAX_AGE": 0,
    }


def build_cache_config():
    redis_url = os.getenv("REDIS_URL", "").strip()
    if redis_url and package_available("django_redis"):
        return {
            "default": {
                "BACKEND": "django_redis.cache.RedisCache",
                "LOCATION": redis_url,
                "OPTIONS": {
                    "CLIENT_CLASS": "django_redis.client.DefaultClient",
                    "IGNORE_EXCEPTIONS": True,
                },
                "TIMEOUT": env_int("CACHE_DEFAULT_TIMEOUT", 300),
            }
        }

    return {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "ai-sakhi-cache",
            "TIMEOUT": env_int("CACHE_DEFAULT_TIMEOUT", 300),
        }
    }


SECRET_KEY = os.getenv("SECRET_KEY", "change-me-for-production")
# Default to local-friendly behavior; production should set DEBUG=False.
DEBUG = env_bool("DEBUG", True)

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "127.0.0.1,localhost,testserver")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", "")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "women_app",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
]

if package_available("whitenoise"):
    MIDDLEWARE.append("whitenoise.middleware.WhiteNoiseMiddleware")

MIDDLEWARE += [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "women_app.middleware.SimpleRateLimitMiddleware",
    "women_app.middleware.AuditLogMiddleware",
]

ROOT_URLCONF = "ai_sakhi.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "women_app" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

WSGI_APPLICATION = "ai_sakhi.wsgi.application"

DATABASES = {"default": build_database_config()}
CACHES = build_cache_config()

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
STATICFILES_DIRS = [BASE_DIR / "women_app" / "static"]

if package_available("whitenoise") and not DEBUG:
    STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "/admin/login/"

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = env_bool("USE_X_FORWARDED_HOST", True)

SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
CSRF_COOKIE_SAMESITE = os.getenv("CSRF_COOKIE_SAMESITE", "Lax")
CSRF_COOKIE_HTTPONLY = env_bool("CSRF_COOKIE_HTTPONLY", False)

secure_defaults_enabled = not DEBUG and not RUNNING_TESTS
SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", secure_defaults_enabled)
CSRF_COOKIE_SECURE = env_bool("CSRF_COOKIE_SECURE", secure_defaults_enabled)
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", secure_defaults_enabled)
SECURE_HSTS_SECONDS = env_int("SECURE_HSTS_SECONDS", 31536000 if secure_defaults_enabled else 0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", secure_defaults_enabled)
SECURE_HSTS_PRELOAD = env_bool("SECURE_HSTS_PRELOAD", secure_defaults_enabled)

# Keep local runserver usable even if the shell has production-style env vars.
if RUNNING_DEV_SERVER and not RUNNING_TESTS:
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    SECURE_SSL_REDIRECT = False
    SECURE_HSTS_SECONDS = 0
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = os.getenv("SECURE_REFERRER_POLICY", "strict-origin-when-cross-origin")

DATA_UPLOAD_MAX_MEMORY_SIZE = env_int("DATA_UPLOAD_MAX_MEMORY_SIZE", 4 * 1024 * 1024)
FILE_UPLOAD_MAX_MEMORY_SIZE = env_int("FILE_UPLOAD_MAX_MEMORY_SIZE", 2 * 1024 * 1024)

RATE_LIMIT_ENABLED = env_bool("RATE_LIMIT_ENABLED", True)
RATE_LIMIT_WINDOW_SECONDS = env_int("RATE_LIMIT_WINDOW_SECONDS", 60)
AUDIT_LOG_READ_REQUESTS = env_bool("AUDIT_LOG_READ_REQUESTS", False)
