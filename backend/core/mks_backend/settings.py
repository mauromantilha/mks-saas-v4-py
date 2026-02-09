import importlib.util
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

USE_X_FORWARDED_HOST = env.bool("USE_X_FORWARDED_HOST", default=True)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

DATABASE_ENGINE = env("DATABASE_ENGINE", default="django_tenants.postgresql_backend").strip()
DJANGO_TENANTS_ENABLED = DATABASE_ENGINE == "django_tenants.postgresql_backend"

# django-tenants: tenant metadata is stored in the public schema.
TENANT_MODEL = "customers.Company"
TENANT_DOMAIN_MODEL = "customers.Domain"
SHOW_PUBLIC_IF_NO_TENANT_FOUND = env.bool("SHOW_PUBLIC_IF_NO_TENANT_FOUND", default=True)

guardian_available = importlib.util.find_spec("guardian") is not None
if DJANGO_TENANTS_ENABLED:
    SHARED_APPS = [
        "django_tenants",
        "django.contrib.admin",
        "django.contrib.auth",
        "django.contrib.contenttypes",
        "django.contrib.sessions",
        "django.contrib.messages",
        "django.contrib.staticfiles",
        "corsheaders",
        "rest_framework",
        "rest_framework.authtoken",
        "tenancy.apps.TenancyConfig",
        "customers.apps.CustomersConfig",
        "control_plane.apps.ControlPlaneConfig",
    ]

    TENANT_APPS = [
        # NOTE: We keep `auth` and `contenttypes` in the public schema to share users/tokens
        # across all tenants and the control plane. Tenant schemas will access those tables
        # via `search_path` (tenant schema + public).
        "tenancy.apps.TenancyConfig",
        "operational.apps.OperationalConfig",
        "insurance_core.apps.InsuranceCoreConfig",
        "ledger.apps.LedgerConfig",
    ]

    if guardian_available:
        # Guardian tables must exist in tenant schemas. We also keep them in public
        # to avoid backend permission checks crashing on the control plane.
        SHARED_APPS.append("guardian")
        TENANT_APPS.append("guardian")
        AUTHENTICATION_BACKENDS = (
            "django.contrib.auth.backends.ModelBackend",
            "guardian.backends.ObjectPermissionBackend",
        )
        ANONYMOUS_USER_ID = -1
    else:
        AUTHENTICATION_BACKENDS = ("django.contrib.auth.backends.ModelBackend",)

    INSTALLED_APPS = SHARED_APPS + [app for app in TENANT_APPS if app not in SHARED_APPS]

    DATABASE_ROUTERS = ("django_tenants.routers.TenantSyncRouter",)
    ROOT_URLCONF = "mks_backend.urls_tenant"
    PUBLIC_SCHEMA_URLCONF = "mks_backend.urls_public"

    MIDDLEWARE = [
        # Must be at the top: selects schema based on host / header fallback.
        "tenancy.middleware.MksTenantMainMiddleware",
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
else:
    # Legacy mode (sqlite, etc.) - no schema-per-tenant.
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
        "tenancy.apps.TenancyConfig",
        "control_plane.apps.ControlPlaneConfig",
        "customers.apps.CustomersConfig",
        "operational.apps.OperationalConfig",
        "insurance_core.apps.InsuranceCoreConfig",
        "ledger.apps.LedgerConfig",
    ]
    if guardian_available:
        INSTALLED_APPS.append("guardian")
        AUTHENTICATION_BACKENDS = (
            "django.contrib.auth.backends.ModelBackend",
            "guardian.backends.ObjectPermissionBackend",
        )
        ANONYMOUS_USER_ID = -1
    else:
        AUTHENTICATION_BACKENDS = ("django.contrib.auth.backends.ModelBackend",)

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

database_engine = DATABASE_ENGINE
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
TENANT_BASE_DOMAIN = env("TENANT_BASE_DOMAIN", default="").strip().lower()
TENANT_REQUIRED_PATH_PREFIXES = env.list("TENANT_REQUIRED_PATH_PREFIXES", default=["/api/"])
TENANT_EXEMPT_PATH_PREFIXES = env.list(
    "TENANT_EXEMPT_PATH_PREFIXES",
    default=["/api/auth/token/", "/api/auth/me/"],
)
CONTROL_PLANE_SUBDOMAIN = env("CONTROL_PLANE_SUBDOMAIN", default="sistema").strip().lower()
CONTROL_PLANE_HOST = env("CONTROL_PLANE_HOST", default="").strip().lower()
if not CONTROL_PLANE_HOST and TENANT_BASE_DOMAIN and CONTROL_PLANE_SUBDOMAIN:
    CONTROL_PLANE_HOST = f"{CONTROL_PLANE_SUBDOMAIN}.{TENANT_BASE_DOMAIN}"

tenant_public_hosts = [
    host.strip().lower()
    for host in env.list(
    "TENANT_PUBLIC_HOSTS",
    default=["localhost", "127.0.0.1", "testserver"],
    )
    if host.strip()
]
if CONTROL_PLANE_HOST and CONTROL_PLANE_HOST not in tenant_public_hosts:
    tenant_public_hosts.append(CONTROL_PLANE_HOST)
TENANT_PUBLIC_HOSTS = tenant_public_hosts
TENANT_RESERVED_SUBDOMAINS = [
    subdomain.strip().lower()
    for subdomain in env.list(
        "TENANT_RESERVED_SUBDOMAINS",
        default=["sistema", "www", "api", "admin", "static", "media"],
    )
    if subdomain.strip()
]
if CONTROL_PLANE_SUBDOMAIN and CONTROL_PLANE_SUBDOMAIN not in TENANT_RESERVED_SUBDOMAINS:
    TENANT_RESERVED_SUBDOMAINS.append(CONTROL_PLANE_SUBDOMAIN)
CONTROL_PLANE_ALLOWED_HOSTS = [
    host.strip().lower()
    for host in env.list(
        "CONTROL_PLANE_ALLOWED_HOSTS",
        default=["localhost", "127.0.0.1", "testserver"],
    )
    if host.strip()
]
if CONTROL_PLANE_HOST and CONTROL_PLANE_HOST not in CONTROL_PLANE_ALLOWED_HOSTS:
    CONTROL_PLANE_ALLOWED_HOSTS.append(CONTROL_PLANE_HOST)

raw_tenant_role_matrices = env("TENANT_ROLE_MATRICES", default="")
try:
    TENANT_ROLE_MATRICES = (
        json.loads(raw_tenant_role_matrices) if raw_tenant_role_matrices else {}
    )
except json.JSONDecodeError:
    TENANT_ROLE_MATRICES = {}

CONTROL_PLANE_PROVISIONER = env("CONTROL_PLANE_PROVISIONER", default="noop")
CONTROL_PLANE_PORTAL_URL_TEMPLATE = env("CONTROL_PLANE_PORTAL_URL_TEMPLATE", default="")
CONTROL_PLANE_LOCAL_DB_ADMIN_DATABASE = env(
    "CONTROL_PLANE_LOCAL_DB_ADMIN_DATABASE",
    default="postgres",
)
CONTROL_PLANE_LOCAL_DB_ADMIN_USER = env("CONTROL_PLANE_LOCAL_DB_ADMIN_USER", default="")
CONTROL_PLANE_LOCAL_DB_ADMIN_PASSWORD = env(
    "CONTROL_PLANE_LOCAL_DB_ADMIN_PASSWORD",
    default="",
)
CONTROL_PLANE_LOCAL_DB_ADMIN_HOST = env(
    "CONTROL_PLANE_LOCAL_DB_ADMIN_HOST",
    default=env("DATABASE_HOST", default="127.0.0.1"),
)
CONTROL_PLANE_LOCAL_DB_ADMIN_PORT = env.int(
    "CONTROL_PLANE_LOCAL_DB_ADMIN_PORT",
    default=env.int("DATABASE_PORT", default=5432),
)
CONTROL_PLANE_LOCAL_DB_PASSWORD_DEFAULT = env(
    "CONTROL_PLANE_LOCAL_DB_PASSWORD_DEFAULT",
    default="change-me-tenant-password",
)
CONTROL_PLANE_CLOUDSQL_ADMIN_DATABASE = env(
    "CONTROL_PLANE_CLOUDSQL_ADMIN_DATABASE",
    default="postgres",
)
CONTROL_PLANE_CLOUDSQL_ADMIN_USER = env("CONTROL_PLANE_CLOUDSQL_ADMIN_USER", default="")
CONTROL_PLANE_CLOUDSQL_ADMIN_PASSWORD = env(
    "CONTROL_PLANE_CLOUDSQL_ADMIN_PASSWORD",
    default="",
)
CONTROL_PLANE_CLOUDSQL_ADMIN_HOST = env("CONTROL_PLANE_CLOUDSQL_ADMIN_HOST", default="")
CONTROL_PLANE_CLOUDSQL_ADMIN_PORT = env.int(
    "CONTROL_PLANE_CLOUDSQL_ADMIN_PORT",
    default=5432,
)
CONTROL_PLANE_CLOUDSQL_ADMIN_SSLMODE = env(
    "CONTROL_PLANE_CLOUDSQL_ADMIN_SSLMODE",
    default="disable",
)
CONTROL_PLANE_CLOUDSQL_TENANT_PASSWORD_DEFAULT = env(
    "CONTROL_PLANE_CLOUDSQL_TENANT_PASSWORD_DEFAULT",
    default="change-me-tenant-password",
)

VERTEX_AI_ENABLED = env.bool("VERTEX_AI_ENABLED", default=False)
VERTEX_AI_PROJECT_ID = env(
    "VERTEX_AI_PROJECT_ID",
    default=env("GOOGLE_CLOUD_PROJECT", default=""),
).strip()
VERTEX_AI_LOCATION = env("VERTEX_AI_LOCATION", default="us-central1").strip()
VERTEX_AI_MODEL = env("VERTEX_AI_MODEL", default="gemini-1.5-pro-002").strip()
VERTEX_AI_TEMPERATURE = env.float("VERTEX_AI_TEMPERATURE", default=0.2)

CNPJ_LOOKUP_ENDPOINT = env("CNPJ_LOOKUP_ENDPOINT", default="").strip()
CNPJ_LOOKUP_TIMEOUT_SECONDS = env.float("CNPJ_LOOKUP_TIMEOUT_SECONDS", default=8.0)

CEP_LOOKUP_ENDPOINT = env(
    "CEP_LOOKUP_ENDPOINT",
    default="https://viacep.com.br/ws/{cep}/json/",
).strip()
CEP_LOOKUP_TIMEOUT_SECONDS = env.float("CEP_LOOKUP_TIMEOUT_SECONDS", default=6.0)

EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend",
)
DEFAULT_FROM_EMAIL = env(
    "DEFAULT_FROM_EMAIL",
    default=f"no-reply@{TENANT_BASE_DOMAIN or 'localhost'}",
)
