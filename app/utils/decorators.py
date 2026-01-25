"""
Night-Walk MVP - RBAC Decorators
"""
from functools import wraps
from flask import abort, flash, redirect, url_for, g
from flask_login import current_user, login_required

# Role constants
ROLE_ADMIN = 'admin'
ROLE_OWNER = 'owner'
ROLE_STAFF = 'staff'

# Permission matrix
PERMISSIONS = {
    'vacancy.update': [ROLE_ADMIN, ROLE_OWNER, ROLE_STAFF],
    'shop.view': [ROLE_ADMIN, ROLE_OWNER, ROLE_STAFF],
    'shop.edit': [ROLE_ADMIN, ROLE_OWNER],
    'job.manage': [ROLE_ADMIN, ROLE_OWNER],
    'billing.view': [ROLE_ADMIN, ROLE_OWNER],
    'admin.access': [ROLE_ADMIN],
}


def admin_required(f):
    """Decorator to require admin role."""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            flash('この操作には管理者権限が必要です。', 'danger')
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


def owner_required(f):
    """Decorator to require owner role for the current shop."""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if current_user.is_admin:
            return f(*args, **kwargs)
        
        shop = getattr(g, 'current_shop', None)
        if not shop:
            flash('店舗が選択されていません。', 'warning')
            return redirect(url_for('shop_admin.select_shop'))
        
        membership = current_user.shop_memberships.filter_by(shop_id=shop.id).first()
        if not membership or membership.role != ROLE_OWNER:
            flash('この操作にはオーナー権限が必要です。', 'danger')
            abort(403)
        
        return f(*args, **kwargs)
    return decorated_function


def shop_access_required(f):
    """Decorator to require access to the current shop."""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if current_user.is_admin:
            return f(*args, **kwargs)
        
        shop = getattr(g, 'current_shop', None)
        if not shop:
            flash('店舗が選択されていません。', 'warning')
            return redirect(url_for('shop_admin.select_shop'))
        
        if not current_user.can_access_shop(shop.id):
            flash('この店舗へのアクセス権限がありません。', 'danger')
            abort(403)
        
        return f(*args, **kwargs)
    return decorated_function


def permission_required(permission):
    """Decorator factory to require a specific permission."""
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            shop = getattr(g, 'current_shop', None)
            shop_id = shop.id if shop else kwargs.get('shop_id')
            
            if not current_user.has_permission(permission, shop_id):
                flash('この操作の権限がありません。', 'danger')
                abort(403)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator
