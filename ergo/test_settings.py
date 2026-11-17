"""Dependency-light settings for ERGO's regression suite.

These settings never read ``.env`` and never touch the configured MySQL
instance. Django creates the current models directly in an in-memory SQLite
database, while e-mail and uploaded files stay in temporary local backends.
"""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = 'ergo-test-only-secret'
DEBUG = False
ALLOWED_HOSTS = ['testserver', 'localhost', '127.0.0.1']

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
    'units',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'ergo.urls'
TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'templates'],
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
            'widget_tweaks': 'ergo.test_widget_tweaks',
        },
    },
}]

DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
AUTH_USER_MODEL = 'accounts.CustomUser'
AUTHENTICATION_BACKENDS = ['django.contrib.auth.backends.ModelBackend']
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']

LANGUAGE_CODE = 'en-us'
LANGUAGES = [('en', 'English'), ('pt-br', 'Portuguese (Brazil)')]
LOCALE_PATHS = [BASE_DIR / 'locale']
TIME_ZONE = 'America/Recife'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'test_static'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'test_media'
PRIVATE_MEDIA_ROOT = BASE_DIR / 'test_private_media'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
DEFAULT_FROM_EMAIL = 'Ergo Tests <noreply@example.invalid>'
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/tasks/'
SESSION_COOKIE_NAME = 'ergo_test_sessionid'
CSRF_COOKIE_NAME = 'ergo_test_csrftoken'

# Current-model tests intentionally skip the legacy MySQL migration history.
MIGRATION_MODULES = {
    app: None
    for app in (
        'accounts', 'tasks', 'upgrades', 'user_aspects', 'user_dimensions',
        'dimensions', 'units', 'pages', 'users',
    )
}
