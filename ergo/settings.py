"""Django settings for ERGO v5.

Runtime configuration is loaded from ``.env``. See ``.env.example`` and the
deployment documentation before running outside a development machine.
"""

import os
import dj_database_url
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / '.env', override=False)


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
DEBUG = os.environ.get('DEBUG', 'True').lower() in {'1', 'true', 'yes', 'on'}

SECRET_KEY = os.environ.get('SECRET_KEY', '').strip()
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = 'django-insecure-development-only-change-me'
    else:
        raise ImproperlyConfigured('SECRET_KEY must be set when DEBUG=False.')

ALLOWED_HOSTS = [
    value.strip()
    for value in os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')
    if value.strip()
]

# Public share links hide participant identities by default. Set to True only
# when every participant has consented to public name disclosure.
PUBLIC_SHARE_SHOW_PARTICIPANT_NAMES = os.environ.get(
    'PUBLIC_SHARE_SHOW_PARTICIPANT_NAMES', 'False'
).lower() in {'1', 'true', 'yes', 'on'}

INTERNAL_IPS = [
    "127.0.0.1",
]

# Configure complete origins (scheme + host) through the environment.
CSRF_TRUSTED_ORIGINS = [
    value.strip()
    for value in os.environ.get('CSRF_TRUSTED_ORIGINS', '').split(',')
    if value.strip()
]

# Security settings for production (HTTPS)
if not DEBUG:
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = False  # Set to True if reverse proxy doesn't handle HTTPS redirect
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True

# Application definition

INSTALLED_APPS = [
    'pages.apps.PagesConfig',
    'dimensions.apps.DimensionsConfig',
    'user_aspects.apps.UserAspectsConfig',
    'user_dimensions.apps.UserDimensionsConfig',
    'tasks.apps.TasksConfig',
    'upgrades.apps.UpgradesConfig',
    'users.apps.UsersConfig',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'accounts',
    'widget_tweaks',
    'units',
    'django_extensions',
    'axes',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'axes.middleware.AxesMiddleware',
    'ergo.middleware.CSPMiddleware',
]

# Debug Toolbar: only load in development
if DEBUG:
    INSTALLED_APPS += ['debug_toolbar']
    MIDDLEWARE += ['debug_toolbar.middleware.DebugToolbarMiddleware']

ROOT_URLCONF = 'ergo.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [Path.joinpath(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'ergo.context_processors.ergo_context',
            ],
            'libraries': {
                'task_extras': 'tasks.templatetags.task_extras',
            }
        },
    },
]

WSGI_APPLICATION = 'ergo.wsgi.application'


# Database
# Use DATABASE_URL from environment for Supabase/Production
DATABASE_URL = os.environ.get('DATABASE_URL', '').strip()
if not DATABASE_URL:
    raise ImproperlyConfigured(
        'DATABASE_URL is not configured. Copy .env.example to .env and set a valid database URL.'
    )

DATABASES = {
    'default': dj_database_url.parse(
        DATABASE_URL,
        conn_max_age=0,
    )
}



# Password validation
# https://docs.djangoproject.com/en/4.1/ref/settings/#auth-password-validators

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

AUTH_USER_MODEL = 'accounts.CustomUser'

# Authentication URLs
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/tasks/'

# Internationalization
# https://docs.djangoproject.com/en/4.1/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'America/Recife'

USE_I18N = True

USE_TZ = True

LANGUAGES = [
    ('en', 'English'),
    ('pt-br', 'Portuguese (Brazil)'),
]

LOCALE_PATHS = [
    os.path.join(BASE_DIR, 'locale'),
]


## Static files (CSS, JavaScript, Images)
STATIC_ROOT = Path.joinpath(BASE_DIR, 'static')
STATIC_URL = '/static/'
STATICFILES_DIRS = [
    Path.joinpath(BASE_DIR, 'ergo', 'static')
]
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage',
    },
}
WHITENOISE_MANIFEST_STRICT = False

# Default primary key field type
# https://docs.djangoproject.com/en/4.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Password reset link timeout (20 minutes)
PASSWORD_RESET_TIMEOUT = 1200

# Session Settings (1 hour)
SESSION_COOKIE_AGE = 3600  # 1 hour in seconds
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_SAVE_EVERY_REQUEST = True

AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesStandaloneBackend',
    'accounts.backends.EmailOrUsernameModelBackend',
]

# Django Axes - Brute Force Protection
AXES_FAILURE_LIMIT = 5                 # Bloqueia após 5 tentativas falhas
AXES_COOLOFF_TIME = 0.5                # Desbloqueia após 30 minutos (0.5 hora)
AXES_RESET_ON_SUCCESS = True           # Reseta contador após login com sucesso
AXES_LOCKOUT_PARAMETERS = ['username', 'ip_address']  # Bloqueia por usuário+IP
AXES_IPWARE_META_PRECEDENCE_ORDER = ['HTTP_X_FORWARDED_FOR', 'REMOTE_ADDR'] # Lê o IP real por trás do Apache
AXES_LOCKOUT_TEMPLATE = 'lockout.html' # Página estilizada para bloqueios

DATE_INPUT_FORMATS = ['%m/%d/%Y']

# Email Settings
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True') == 'True'
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'Ergo <noreply@ergo.com>')
EMAIL_REPLY_TO = os.environ.get('EMAIL_REPLY_TO')

# Messages
from django.contrib.messages import constants as messages

MESSAGE_TAGS = {
    messages.ERROR: 'danger'
}

# Production Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}

# Cookie Settings for Isolation
SESSION_COOKIE_NAME = 'ergo2_sessionid'
CSRF_COOKIE_NAME = 'ergo2_csrftoken'

import subprocess
import datetime

def get_app_version():
    # 1. Tenta obter a data do último commit do Git
    try:
        version = subprocess.check_output(
            ['git', 'log', '-1', '--format=%cd', '--date=format:V-%d.%m.%Y-%H:%M'],
            stderr=subprocess.DEVNULL,
            cwd=os.path.dirname(os.path.abspath(__file__))
        ).decode('utf-8').strip()
        if version:
            return version
    except Exception:
        pass

    # 2. Fallback: Data de modificação do arquivo settings.py (data do deploy/build)
    try:
        mtime = os.path.getmtime(__file__)
        return datetime.datetime.fromtimestamp(mtime).strftime('V-%d.%m.%Y-%H:%M')
    except Exception:
        pass

    # 3. Fallback final: Data e hora atual (momento que o servidor iniciou)
    return datetime.datetime.now().strftime('V-%d.%m.%Y-%H:%M')

# App Version (Automated with Fallbacks)
APP_VERSION = get_app_version()
if DEBUG:
    import time
    APP_VERSION += f"-{int(time.time())}"

# Media files used by the task collaboration/attachment upgrades
MEDIA_URL = '/media/'
MEDIA_ROOT = Path.joinpath(BASE_DIR, 'media')

# Private files are served only through authorization-checked views.
PRIVATE_MEDIA_ROOT = Path(
    os.environ.get('PRIVATE_MEDIA_ROOT') or Path.joinpath(BASE_DIR, 'private_media')
).resolve()
