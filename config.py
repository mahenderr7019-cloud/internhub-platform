import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', 'admin@internhub.com')
    ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')

    RAZORPAY_KEY_ID = os.getenv('RAZORPAY_KEY_ID', '')
    RAZORPAY_KEY_SECRET = os.getenv('RAZORPAY_KEY_SECRET', '')
    GUMLET_API_KEY = os.getenv('GUMLET_API_KEY', '')

    # Force psycopg2 driver (psycopg3 has IPv6 issues on Render free tier)
    _db_url = os.getenv('DATABASE_URL', 'sqlite:///database.db')
    if _db_url:
        if _db_url.startswith("postgres://"):
            _db_url = _db_url.replace("postgres://", "postgresql+psycopg2://", 1)
        elif _db_url.startswith("postgresql+psycopg://"):
            _db_url = _db_url.replace("postgresql+psycopg://", "postgresql+psycopg2://", 1)
        elif _db_url.startswith("postgresql://"):
            _db_url = _db_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    SQLALCHEMY_DATABASE_URI = _db_url