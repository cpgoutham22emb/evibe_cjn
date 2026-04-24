from .base import *

DEBUG = False

ALLOWED_HOSTS = ["evibe-cjn.onrender.com"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}