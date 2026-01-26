"""
Night-Walk MVP - Configuration
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Base configuration."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-me')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Application
    APP_NAME = os.environ.get('APP_NAME', 'Night-Walk')
    DEFAULT_AREA = os.environ.get('DEFAULT_AREA', '岡山')
    
    # Twilio
    TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
    TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
    TWILIO_PHONE_NUMBER = os.environ.get('TWILIO_PHONE_NUMBER')
    
    # Stripe
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY')
    STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY')
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')
    STRIPE_PRICE_ID_BASIC = os.environ.get('STRIPE_PRICE_ID_BASIC')
    
    # SendGrid (Email)
    SENDGRID_API_KEY = os.environ.get('SENDGRID_API_KEY')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@night-walk.jp')
    
    # Company Info (for invoices)
    COMPANY_INFO = {
        'name': os.environ.get('COMPANY_NAME', 'Night-Walk運営事務局'),
        'postal_code': os.environ.get('COMPANY_POSTAL_CODE', '700-0000'),
        'address': os.environ.get('COMPANY_ADDRESS', '岡山県岡山市北区XX町1-2-3'),
        'phone': os.environ.get('COMPANY_PHONE', '086-XXX-XXXX'),
        'email': os.environ.get('COMPANY_EMAIL', 'billing@night-walk.jp'),
        'bank_name': os.environ.get('COMPANY_BANK_NAME', 'XXX銀行 YYY支店'),
        'bank_account_type': os.environ.get('COMPANY_BANK_TYPE', '普通'),
        'bank_account_number': os.environ.get('COMPANY_BANK_NUMBER', '1234567'),
        'bank_account_holder': os.environ.get('COMPANY_BANK_HOLDER', 'ナイトウォーク（カ'),
    }
    
    # Upload
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    UPLOAD_FOLDER = 'app/static/uploads'
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL', 'sqlite:///night_walk.db'
    )


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    
    # Get DATABASE_URL directly - Render provides postgresql:// format
    _db_url = os.environ.get('DATABASE_URL', '')
    # Fix for older postgres:// URL format
    if _db_url.startswith('postgres://'):
        _db_url = _db_url.replace('postgres://', 'postgresql://', 1)
    SQLALCHEMY_DATABASE_URI = _db_url if _db_url else None


class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
