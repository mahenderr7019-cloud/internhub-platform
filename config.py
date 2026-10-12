import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', 'admin@internhub.com')
    ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')

    # Razorpay
    RAZORPAY_KEY_ID = os.getenv('RAZORPAY_KEY_ID', '')
    RAZORPAY_KEY_SECRET = os.getenv('RAZORPAY_KEY_SECRET', '')

    # Gumlet
    GUMLET_API_KEY = os.getenv('GUMLET_API_KEY', '')

    # Email (Gmail SMTP)
    MAIL_SERVER = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.getenv('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD', '')
    MAIL_SENDER_NAME = os.getenv('MAIL_SENDER_NAME', 'InternHub')

    # Database URL
    _db_url = os.getenv('DATABASE_URL', 'sqlite:///database.db')
    if _db_url:
        if _db_url.startswith("postgres://"):
            _db_url = _db_url.replace("postgres://", "postgresql+psycopg2://", 1)
        elif _db_url.startswith("postgresql+psycopg://"):
            _db_url = _db_url.replace("postgresql+psycopg://", "postgresql+psycopg2://", 1)
        elif _db_url.startswith("postgresql://"):
            _db_url = _db_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    SQLALCHEMY_DATABASE_URI = _db_url

    # ⭐ Fix for Neon SSL drop / connection recycling
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,        # Test connection before using it
        "pool_recycle": 300,          # Recycle connections after 5 minutes
        "pool_size": 5,               # Keep 5 connections ready
        "max_overflow": 2,            # Allow 2 extra during spikes
        "connect_args": {
            "connect_timeout": 10,    # Give Neon time to wake up
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 10,
            "keepalives_count": 5,
        },
    }