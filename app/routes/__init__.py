"""
Night-Walk MVP - Routes
"""
from .auth import auth_bp
from .admin import admin_bp
from .shop_admin import shop_admin_bp
from .public import public_bp
from .api import api_bp
from .webhook import webhook_bp

__all__ = [
    'auth_bp',
    'admin_bp',
    'shop_admin_bp',
    'public_bp',
    'api_bp',
    'webhook_bp',
]
