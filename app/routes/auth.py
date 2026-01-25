"""
Night-Walk MVP - Authentication Routes
"""
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from ..extensions import db, limiter
from ..models.user import User
from ..models.audit import AuditLog
from ..utils.logger import audit_log

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute", methods=["POST"])
def login():
    """Login page."""
    if current_user.is_authenticated:
        return redirect(get_redirect_url())
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember = request.form.get('remember', False)
        
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            if not user.is_active:
                flash('このアカウントは無効化されています。', 'danger')
                audit_log(AuditLog.ACTION_USER_LOGIN_FAILED, 'user', user.id,
                         new_value={'reason': 'account_disabled'})
                return render_template('auth/login.html')
            
            # Successful login
            login_user(user, remember=remember)
            user.last_login_at = datetime.utcnow()
            db.session.commit()
            
            audit_log(AuditLog.ACTION_USER_LOGIN, 'user', user.id)
            
            flash(f'ようこそ、{user.name}さん！', 'success')
            
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(get_redirect_url())
        
        # Failed login
        flash('メールアドレスまたはパスワードが正しくありません。', 'danger')
        audit_log(AuditLog.ACTION_USER_LOGIN_FAILED, 'user', None,
                 new_value={'email': email, 'reason': 'invalid_credentials'})
    
    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    """Logout."""
    audit_log(AuditLog.ACTION_USER_LOGOUT, 'user', current_user.id)
    logout_user()
    flash('ログアウトしました。', 'info')
    return redirect(url_for('auth.login'))


def get_redirect_url():
    """Get appropriate redirect URL after login."""
    if current_user.is_admin:
        return url_for('admin.dashboard')
    return url_for('shop_admin.dashboard')
