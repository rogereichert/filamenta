""

from pathlib import Path
import os

from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env before reading any env vars
load_dotenv(BASE_DIR / ".env")

# ==========================
# Email (Gmail SMTP + certifi)
# ==========================
# NOTE: Gmail recomenda "Senha de app" (2FA habilitado).
EMAIL_BACKEND = "apps.core.email_backend.CertifiSMTPEmailBackend"
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_USE_SSL = False

EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")

# Timeout do SMTP (segundos). Ajuda a não travar a requisição por muito tempo
# em redes lentas ou quando o servidor demora para responder.
EMAIL_TIMEOUT = int(os.getenv("EMAIL_TIMEOUT", "15"))

DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER)
PEDIDO_DESTINO_EMAIL = os.getenv("PEDIDO_DESTINO_EMAIL", "contato.filamenta@gmail.com")

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "unsafe-secret-key")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv("DJANGO_DEBUG", "false").lower() == "true"

ALLOWED_HOSTS = [h.strip() for h in os.getenv('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',') if h.strip()]


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'widget_tweaks',
    'apps.core',
    'apps.clientes',
    'apps.filamentos',
    'apps.pedidos',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    # Requer login por padrão (exceto /accounts/, /admin/, static/media)
    'apps.core.middleware.LoginRequiredMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        "DIRS": [BASE_DIR / "templates"],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Database
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases

DATABASES = {
    "default": {
        # Se as variáveis do Postgres não estiverem definidas, cai para SQLite
        "ENGINE": os.getenv("DB_ENGINE", "django.db.backends.postgresql"),
        "NAME": os.getenv("DB_NAME") or (BASE_DIR / "db.sqlite3"),
        "USER": os.getenv("DB_USER", ""),
        "PASSWORD": os.getenv("DB_PASSWORD", ""),
        "HOST": os.getenv("DB_HOST", "localhost"),
        "PORT": os.getenv("DB_PORT", "5432"),
    }
}

# Ajusta automaticamente para SQLite caso DB_NAME não exista
if not os.getenv("DB_NAME"):
    DATABASES["default"]["ENGINE"] = "django.db.backends.sqlite3"
    DATABASES["default"].pop("USER", None)
    DATABASES["default"].pop("PASSWORD", None)
    DATABASES["default"].pop("HOST", None)
    DATABASES["default"].pop("PORT", None)


# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = 'pt-br'

TIME_ZONE = os.getenv('DJANGO_TIME_ZONE', 'America/Recife')

USE_I18N = True

USE_TZ = True


# Authentication
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/accounts/login/"


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/

STATIC_URL = '/static/'


# Onde o `collectstatic` irá juntar os arquivos estáticos (produção)
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

# Uploads
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Auth

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Segurança básica quando DEBUG=False
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = os.getenv("DJANGO_SECURE_SSL_REDIRECT", "false").lower() == "true"
    SECURE_HSTS_SECONDS = int(os.getenv("DJANGO_SECURE_HSTS_SECONDS", "0"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = os.getenv("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", "false").lower() == "true"
    SECURE_HSTS_PRELOAD = os.getenv("DJANGO_SECURE_HSTS_PRELOAD", "false").lower() == "true"
