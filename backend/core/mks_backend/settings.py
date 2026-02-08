import json
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1", "testserver"]),
    CORS_ALLOWED_ORIGINS=(list, []),
    CSRF_TRUSTED_ORIGINS=(list, []),
)
environ.Env.read_env(BASE_DIR / ".env")


def read_secret_from_manager(secret_resource: str, default_value: str = "") -> str:
    """
    Reads a secret value from GCP Secret Manager.

    Expected format:
    projects/<project-id>/secrets/<secret-name>
    or
    projects/<project-id>/secrets/<secret-name>/versions/<version>
    """

    if not secret_resource:
        return default_value

    try:
        from google.cloud import secretmanager

        client = secretmanager.SecretManagerServiceClient()
        full_secret_name = secret_resource
        if "/versions/" not in full_secret_name:
            full_secret_name = f"{full_secret_name}/versions/latest"

        response = client.access_secret_version(request={"name": full_secret_name})
        return response.payload.data.decode("utf-8")
    except Exception:
        return default_value


SECRET_KEY = env("SECRET_KEY", default="")
if not SECRET_KEY:
    SECRET_KEY = read_secret_from_manager(
        env("DJANGO_SECRET_KEY_SECRET", default=""),
        default_value="django-insecure-change-me",
    )

DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "rest_framework.authtoken",
    "tenancy",
    "customers",
    "operational",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "tenancy.middleware.TenantContextMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "mks_backend.urls"

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

WSGI_APPLICATION = "mks_backend.wsgi.application"
ASGI_APPLICATION = "mks_backend.asgi.application"

database_password = env("DATABASE_PASSWORD", default="")
if not database_password:
    database_password = read_secret_from_manager(
        env("DATABASE_PASSWORD_SECRET", default=""),
        default_value="",
    )

cloud_sql_instance = env("CLOUD_SQL_INSTANCE", default="")
database_host = (
    f"/cloudsql/{cloud_sql_instance}"
    if cloud_sql_instance
    else env("DATABASE_HOST", default="127.0.0.1")
)
database_port = "" if cloud_sql_instance else env("DATABASE_PORT", default="5432")

database_engine = env("DATABASE_ENGINE", default="django.db.backends.postgresql")
if database_engine == "django.db.backends.sqlite3":
    DATABASES = {
        "default": {
            "ENGINE": database_engine,
            "NAME": env("SQLITE_NAME", default=str(BASE_DIR / "db.sqlite3")),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": database_engine,
            "NAME": env("DATABASE_NAME", default="mks_db"),
            "USER": env("DATABASE_USER", default="mks_user"),
            "PASSWORD": database_password,
            "HOST": database_host,
            "PORT": database_port,
            "CONN_MAX_AGE": env.int("DATABASE_CONN_MAX_AGE", default=60),
            "OPTIONS": (
                {}
                if cloud_sql_instance
                else {"sslmode": env("DATABASE_SSLMODE", default="disable")}
            ),
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
]

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CORS_ALLOWED_ORIGINS = env("CORS_ALLOWED_ORIGINS")
CSRF_TRUSTED_ORIGINS = env("CSRF_TRUSTED_ORIGINS")

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.BasicAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
}

TENANT_ID_HEADER = env("TENANT_ID_HEADER", default="X-Tenant-ID")
TENANT_BASE_DOMAIN = env("TENANT_BASE_DOMAIN", default="")
TENANT_REQUIRED_PATH_PREFIXES = env.list("TENANT_REQUIRED_PATH_PREFIXES", default=["/api/"])
TENANT_EXEMPT_PATH_PREFIXES = env.list(
    "TENANT_EXEMPT_PATH_PREFIXES",
    default=["/api/auth/token/", "/api/auth/me/"],
)
TENANT_PUBLIC_HOSTS = env.list(
    "TENANT_PUBLIC_HOSTS",
    default=["localhost", "127.0.0.1", "testserver"],
)

raw_tenant_role_matrices = env("TENANT_ROLE_MATRICES", default="")
try:
    TENANT_ROLE_MATRICES = (
        json.loads(raw_tenant_role_matrices) if raw_tenant_role_matrices else {}
    )
except json.JSONDecodeError:
    TENANT_ROLE_MATRICES = {}
