"""
Night-Walk MVP - Cast Routes (キャスト用)
キャストが自分のスマホから情報を更新できる機能
"""
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, session, g
from ..extensions import db
from ..models.gift import Cast
from ..models.audit import AuditLog
from ..utils.logger import audit_log

cast_bp = Blueprint('cast', __name__)


def get_current_cast():
    """セッションからログイン中のキャストを取得"""
    cast_id = session.get('cast_id')
    if cast_id:
        return Cast.query.get(cast_id)
    return None


def cast_login_required(f):
    """キャストログイン必須デコレータ"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        cast = get_current_cast()
        if not cast:
            flash('ログインしてください', 'warning')
            return redirect(url_for('cast.login'))
        g.current_cast = cast
        return f(*args, **kwargs)
    return decorated_function


# ============================================
# キャストログイン
# ============================================

@cast_bp.route('/login', methods=['GET', 'POST'])
def login():
    """キャストログイン"""
    if request.method == 'POST':
        login_code = request.form.get('login_code', '').strip()
        pin = request.form.get('pin', '').strip()
        
        if not login_code or not pin:
            flash('ログインコードとPINを入力してください', 'danger')
            return render_template('cast/login.html')
        
        # キャストを検索
        cast = Cast.query.filter_by(login_code=login_code, is_active=True).first()
        
        if not cast or not cast.check_pin(pin):
            flash('ログインコードまたはPINが正しくありません', 'danger')
            return render_template('cast/login.html')
        
        # ログイン成功
        session['cast_id'] = cast.id
        cast.record_login()
        db.session.commit()
        
        flash(f'ようこそ、{cast.name_display}さん！', 'success')
        return redirect(url_for('cast.dashboard'))
    
    return render_template('cast/login.html')


@cast_bp.route('/logout')
def logout():
    """キャストログアウト"""
    session.pop('cast_id', None)
    flash('ログアウトしました', 'info')
    return redirect(url_for('cast.login'))


# ============================================
# キャストダッシュボード
# ============================================

@cast_bp.route('/dashboard')
@cast_login_required
def dashboard():
    """キャストダッシュボード"""
    cast = g.current_cast
    return render_template('cast/dashboard.html', cast=cast)


@cast_bp.route('/update-status', methods=['GET', 'POST'])
@cast_login_required
def update_status():
    """出勤状況更新"""
    cast = g.current_cast
    
    if request.method == 'POST':
        work_status = request.form.get('work_status', Cast.WORK_STATUS_OFF)
        work_start_time = request.form.get('work_start_time', '').strip()
        work_end_time = request.form.get('work_end_time', '').strip()
        work_memo = request.form.get('work_memo', '').strip()
        comment = request.form.get('comment', '').strip()
        
        old_values = {
            'work_status': cast.work_status,
            'comment': cast.comment
        }
        
        cast.work_status = work_status
        cast.work_start_time = work_start_time or None
        cast.work_end_time = work_end_time or None
        cast.work_memo = work_memo[:100] if work_memo else None
        cast.comment = comment[:200] if comment else None
        cast.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        # 監査ログ
        audit_log('cast.status_update', 'cast', cast.id,
                  old_value=old_values,
                  new_value={'work_status': work_status, 'comment': comment})
        
        flash('出勤状況を更新しました', 'success')
        return redirect(url_for('cast.dashboard'))
    
    return render_template('cast/update_status.html', cast=cast)


@cast_bp.route('/profile')
@cast_login_required
def profile():
    """自分のプロフィール確認"""
    cast = g.current_cast
    return render_template('cast/profile.html', cast=cast)
