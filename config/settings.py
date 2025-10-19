import os
from pathlib import Path
from django.contrib.messages import constants as messages
import environ

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Inicializamos environ
env = environ.Env(
    # Creamos valores por defecto y definimos el tipo de variable
    DEBUG=(bool, False)
)

# Leemos el archivo .env que está en la raíz del proyecto (BASE_DIR)
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env('DEBUG')

# Permitimos el acceso desde la URL de ngrok Y desde nuestro entorno de desarrollo local.
ALLOWED_HOSTS = [
    'chatbot-ai-backend-s0h0.onrender.com',  # Render producción
    '7ad8272115d1.ngrok-free.app',  # Para los webhooks de WhatsApp
    'localhost',                   # Para acceder al admin desde tu navegador
    '127.0.0.1',                   # Alias de localhost, es bueno tenerlo también
]

CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",  # Si usas React/Vue
    "http://127.0.0.1:3000",
]

CORS_ALLOW_ALL_ORIGINS = True

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
    'apps.api',
    'apps.reservas',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
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
        'DIRS': [BASE_DIR / 'plantillas'],
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
DATABASES = {
    'default': env.db( ),
}
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql_psycopg2',
#         'NAME': 'motelprats',  # El nombre de la base de datos que creamos
#         'USER': 'postgres',        # El usuario por defecto de PostgreSQL
#         'PASSWORD': '13940525', # ¡IMPORTANTE! Cambia esto por tu contraseña
#         'HOST': 'localhost',       # Donde está corriendo tu base de datos (normalmente localhost)
#         'PORT': '5432',            # El puerto por defecto de PostgreSQL
#     }
# }

# Password validation
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
LANGUAGE_CODE = 'es-cl'
TIME_ZONE = 'America/Santiago'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# WhatsApp Configuration
WHATSAPP_TOKEN = env('WHATSAPP_TOKEN')
WHATSAPP_PHONE_NUMBER_ID = env('WHATSAPP_PHONE_NUMBER_ID')
WHATSAPP_BUSINESS_ACCOUNT_ID = env('WHATSAPP_BUSINESS_ACCOUNT_ID')
VERIFY_TOKEN = env('WHATSAPP_VERIFY_TOKEN')