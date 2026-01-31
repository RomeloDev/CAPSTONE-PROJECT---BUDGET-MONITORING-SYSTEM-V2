import os
from pathlib import Path
from dotenv import load_dotenv
import dj_database_url
import mimetypes

mimetypes.add_type("text/css", ".css", True)

# Load .env file
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-dev-key-change-in-production')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DEBUG', 'False') == 'True'

ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')
CSRF_TRUSTED_ORIGINS = os.getenv('CSRF_TRUSTED_ORIGINS', 'http://localhost:8000').split(',')

# Application definition
INSTALLED_APPS = [
    # Modern Admin (Optional, remove if sticking to default)
    # 'unfold', 
    
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    
    # Third-party
    'django_tailwind_cli', # Simpler Tailwind setup
    'cloudinary_storage',
    'cloudinary',
    
    # Local Apps (Migrate these one by one)
    'apps.user_accounts', 
    'apps.budgets',
    'apps.admin_panel',
    'apps.end_user_panel',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware', # WhiteNoise right after Security
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Database
# Uses dj-database-url for clean switching between SQLite (dev) and Postgres (prod)
DATABASES = {
    'default': dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600
    )
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Manila'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Modern Storage Configuration
STORAGES = {
    "default": {
        "BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# Cloudinary Configuration
CLOUDINARY_STORAGE = {
    'CLOUD_NAME': os.getenv('CLOUDINARY_CLOUD_NAME'),
    'API_KEY': os.getenv('CLOUDINARY_API_KEY'),
    'API_SECRET': os.getenv('CLOUDINARY_API_SECRET'),
}

# Media Files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom User Model
AUTH_USER_MODEL = "user_accounts.User" # Uncomment when you migrate the users app

# Authentication Settings
LOGIN_URL = 'end_user_login'          # Default login page
LOGIN_REDIRECT_URL = '/'              # Where to go after login (we'll change this to dashboard later)
LOGOUT_REDIRECT_URL = 'end_user_login' # Where to go after logout

# Tailwind CLI Configuration
TAILWIND_CLI_MODE = 'jit'
TAILWIND_CLI_SRC_CSS = 'static/css/input.css' # You need to create this
TAILWIND_CLI_DIST_CSS = 'css/output.css'

# ==========================================
# EMAIL CONFIGURATION (Gmail SMTP)
# ==========================================
EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = os.getenv('EMAIL_PORT', 587)
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', True)
# Your Gmail address
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER') 
# The 16-character App Password (NOT your real password)
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD') 
# Password Reset Configuration
# This ensures links point to the correct domain automatically (Localhost or PythonAnywhere)
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER