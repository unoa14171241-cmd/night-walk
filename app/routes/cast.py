"""
Night-Walk MVP - Cast Routes (キャスト用)
キャストが自分のスマホから情報を更新できる機能
RBAC: キャスト本人は自分の情報のみ編集可、店舗側は所属キャスト全員編集可
"""
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, session, g, current_app
from ..extensions import db
from ..models.gift import Cast
from ..models.shop import Shop
from ..models.user import User
from ..models.audit import AuditLog
from ..models.cast_tag import CastTag
from ..models.cast_image import CastImage
from ..models.cast_birthday import CastBirthday
from ..utils.logger import audit_log
from ..services.image_service import resize_and_optimize_image
from ..services.storage_service import upload_image as cloud_upload, delete_image as cloud_delete

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
# キャスト新規登録
# ============================================

@cast_bp.route('/register', methods=['GET', 'POST'])
def register():
    """キャスト新規登録（role: cast）"""
    from werkzeug.security import generate_password_hash
    
    shops = Shop.query.filter_by(is_active=True, is_published=True).order_by(Shop.name).all()
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        display_name = request.form.get('display_name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        shop_id = request.form.get('shop_id', type=int)
        
        errors = []
        if not name:
            errors.append('名前を入力してください')
        if not display_name:
            errors.append('源氏名を入力してください')
        if not email:
            errors.append('メールアドレスを入力してください')
        elif User.query.filter_by(email=email).first():
            errors.append('このメールアドレスは既に使用されています')
        if not password or len(password) < 6:
            errors.append('パスワードは6文字以上で入力してください')
        if not shop_id:
            errors.append('所属店舗を選択してください')
        
        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('cast/register.html', shops=shops,
                                   form_data={'name': name, 'display_name': display_name,
                                              'email': email, 'shop_id': shop_id})
        
        try:
            user = User(email=email, name=name, role=User.ROLE_CAST)
            user.set_password(password)
            db.session.add(user)
            db.session.flush()
            
            import secrets
            login_code = ''.join(secrets.choice('0123456789') for _ in range(8))
            while Cast.query.filter_by(login_code=login_code).first():
                login_code = ''.join(secrets.choice('0123456789') for _ in range(8))
            
            cast = Cast(
                name=name,
                display_name=display_name,
                shop_id=shop_id,
                user_id=user.id,
                approval_status=Cast.APPROVAL_PENDING,
                login_code=login_code,
                is_active=False,
                is_visible=False
            )
            db.session.add(cast)
            db.session.commit()
            
            flash('登録が完了しました。店舗の承認後にプロフィール編集が可能になります。', 'success')
            session['cast_id'] = cast.id
            return redirect(url_for('cast.dashboard'))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Cast registration error: {e}")
            flash('登録処理でエラーが発生しました', 'danger')
            return render_template('cast/register.html', shops=shops,
                                   form_data={'name': name, 'display_name': display_name,
                                              'email': email, 'shop_id': shop_id})
    
    return render_template('cast/register.html', shops=shops, form_data=None)


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
    existing_tags = CastTag.get_tags_by_cast(cast.id)
    existing_birthdays = CastBirthday.get_birthdays(cast.id)
    gallery = CastImage.get_gallery(cast.id)
    return render_template('cast/profile.html', cast=cast,
                           existing_tags=existing_tags,
                           existing_birthdays=existing_birthdays,
                           gallery=gallery)


@cast_bp.route('/edit-profile', methods=['GET', 'POST'])
@cast_login_required
def edit_profile():
    """キャスト自身のプロフィール編集（承認済みのみ）"""
    cast = g.current_cast
    
    if cast.approval_status == Cast.APPROVAL_PENDING:
        flash('店舗からの承認待ちです。承認後にプロフィール編集が可能になります。', 'warning')
        return redirect(url_for('cast.dashboard'))
    
    if cast.approval_status == Cast.APPROVAL_REJECTED:
        flash('登録が承認されませんでした。店舗にお問い合わせください。', 'danger')
        return redirect(url_for('cast.dashboard'))
    
    if request.method == 'POST':
        cast.profile = request.form.get('profile', '').strip()
        cast.twitter_url = request.form.get('twitter_url', '').strip() or None
        cast.instagram_url = request.form.get('instagram_url', '').strip() or None
        cast.tiktok_url = request.form.get('tiktok_url', '').strip() or None
        cast.video_url = request.form.get('video_url', '').strip() or None
        cast.gift_appeal = request.form.get('gift_appeal', '').strip() or None
        cast.updated_at = datetime.utcnow()
        
        # タグ処理
        for category in CastTag.CATEGORIES:
            tag_values = request.form.get(f'tags_{category}', '').strip()
            tag_names = [t.strip() for t in tag_values.split(',') if t.strip()] if tag_values else []
            CastTag.set_tags(cast.id, category, tag_names)
        
        # ギャラリー画像追加
        gallery_files = request.files.getlist('gallery_images')
        existing_count = CastImage.query.filter_by(cast_id=cast.id).count()
        for idx, gfile in enumerate(gallery_files):
            if gfile and gfile.filename:
                try:
                    optimized_data, fmt = resize_and_optimize_image(gfile)
                    if optimized_data:
                        result = cloud_upload(optimized_data, 'casts', filename_prefix=f"cast_{cast.shop_id}_g{existing_count + idx}_")
                        if result:
                            img = CastImage(cast_id=cast.id, filename=result['filename'], sort_order=existing_count + idx)
                            db.session.add(img)
                except Exception as e:
                    current_app.logger.error(f"Cast gallery image upload failed: {e}")
        
        # ギャラリー画像削除
        delete_image_ids = request.form.getlist('delete_gallery_image')
        for img_id in delete_image_ids:
            try:
                img = CastImage.query.get(int(img_id))
                if img and img.cast_id == cast.id:
                    cloud_delete(img.filename, 'casts')
                    db.session.delete(img)
            except (ValueError, Exception) as e:
                current_app.logger.error(f"Gallery image delete failed: {e}")
        
        # 誕生日処理
        CastBirthday.query.filter_by(cast_id=cast.id).delete()
        birthday_entries = request.form.getlist('birthday_date')
        birthday_labels = request.form.getlist('birthday_label')
        for i, bd in enumerate(birthday_entries):
            if bd:
                try:
                    parts = bd.split('-')
                    month = int(parts[0]) if len(parts) == 2 else int(parts[1])
                    day = int(parts[1]) if len(parts) == 2 else int(parts[2])
                    label = birthday_labels[i].strip() if i < len(birthday_labels) else ''
                    cb = CastBirthday(cast_id=cast.id, birthday_month=month, birthday_day=day, label=label or None)
                    db.session.add(cb)
                except (ValueError, IndexError):
                    pass
        
        db.session.commit()
        
        audit_log('cast.profile_update', 'cast', cast.id)
        flash('プロフィールを更新しました', 'success')
        return redirect(url_for('cast.profile'))
    
    existing_tags = CastTag.get_tags_by_cast(cast.id)
    existing_birthdays = CastBirthday.get_birthdays(cast.id)
    gallery = CastImage.get_gallery(cast.id)
    
    return render_template('cast/edit_profile.html', cast=cast,
                           preset_tags=CastTag.PRESET_TAGS, tag_categories=CastTag.CATEGORIES,
                           tag_category_labels=CastTag.CATEGORY_LABELS,
                           existing_tags=existing_tags, existing_birthdays=existing_birthdays,
                           gallery=gallery)
