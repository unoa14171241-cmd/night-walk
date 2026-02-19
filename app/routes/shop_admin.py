"""
Night-Walk MVP - Shop Admin Routes (店舗管理)
"""
import os
import uuid
from datetime import datetime, date, timedelta
from flask import Blueprint, render_template, redirect, url_for, flash, request, g, session, current_app, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from ..extensions import db, limiter
from ..models.shop import Shop, VacancyStatus, VacancyHistory, ShopImage
from ..models.job import Job
from ..models.booking import BookingLog
from ..models.billing import Subscription
from ..models.audit import AuditLog
from ..models.gift import Cast, GiftTransaction
from ..models.earning import Earning
from ..models.cast_tag import CastTag
from ..models.cast_image import CastImage
from ..models.cast_birthday import CastBirthday
from ..utils.decorators import shop_access_required, owner_required
from ..utils.logger import audit_log
from ..utils.helpers import get_client_ip
from ..services.qrcode_service import generate_qrcode_base64, generate_qrcode_svg
from ..services.image_service import resize_and_optimize_image
from ..services.storage_service import upload_image as cloud_upload, delete_image as cloud_delete, get_image_url

shop_admin_bp = Blueprint('shop_admin', __name__)

# Allowed image extensions
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    """Check if file extension is allowed."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_shop_image(file, shop_id):
    """Save uploaded image and return filename (cloud or local)."""
    if not file or not allowed_file(file.filename):
        return None
    
    result = cloud_upload(file, 'shops', filename_prefix=f"{shop_id}_")
    if result:
        return result['filename']
    return None


@shop_admin_bp.before_request
def load_current_shop():
    """Load current shop into g before each request."""
    g.current_shop = None
    
    if not current_user.is_authenticated:
        return
    
    # Admin can access any shop
    if current_user.is_admin:
        shop_id = session.get('admin_shop_id')
        if shop_id:
            g.current_shop = Shop.query.get(shop_id)
        return
    
    # Regular user - get their first shop
    shop = current_user.get_primary_shop()
    if shop:
        g.current_shop = shop


@shop_admin_bp.route('/')
@login_required
def dashboard():
    """Shop dashboard."""
    shop = g.current_shop
    
    if not shop:
        if current_user.is_admin:
            return redirect(url_for('admin.dashboard'))
        flash('所属店舗がありません。管理者にお問い合わせください。', 'warning')
        return redirect(url_for('auth.logout'))
    
    # Today's bookings
    today = date.today()
    today_bookings = BookingLog.query.filter(
        BookingLog.shop_id == shop.id,
        db.func.date(BookingLog.created_at) == today
    ).count()
    
    # Subscription status
    subscription = shop.subscription
    
    # Recent vacancy history
    recent_history = VacancyHistory.query.filter_by(
        shop_id=shop.id
    ).order_by(VacancyHistory.changed_at.desc()).limit(10).all()
    
    return render_template('shop_admin/dashboard.html',
                          shop=shop,
                          today_bookings=today_bookings,
                          subscription=subscription,
                          recent_history=recent_history)


@shop_admin_bp.route('/vacancy', methods=['GET', 'POST'])
@login_required
@shop_access_required
def vacancy():
    """Vacancy status management."""
    shop = g.current_shop
    
    if request.method == 'POST':
        new_status = request.form.get('status')
        
        if new_status not in VacancyStatus.STATUSES:
            flash('無効なステータスです。', 'danger')
            return redirect(url_for('shop_admin.vacancy'))
        
        # Get or create vacancy status
        vacancy_status = shop.vacancy_status
        if not vacancy_status:
            vacancy_status = VacancyStatus(shop_id=shop.id)
            db.session.add(vacancy_status)
        
        old_status = vacancy_status.status
        
        # Update status
        vacancy_status.status = new_status
        vacancy_status.updated_at = datetime.utcnow()
        vacancy_status.updated_by = current_user.id
        
        # Record history
        history = VacancyHistory(
            shop_id=shop.id,
            status=new_status,
            changed_by=current_user.id,
            ip_address=get_client_ip()
        )
        db.session.add(history)
        db.session.commit()
        
        # Audit log
        audit_log(AuditLog.ACTION_VACANCY_UPDATE, 'shop', shop.id,
                 old_value={'status': old_status},
                 new_value={'status': new_status})
        
        status_label = VacancyStatus.STATUS_LABELS.get(new_status, new_status)
        flash(f'空席ステータスを「{status_label}」に更新しました。', 'success')
        return redirect(url_for('shop_admin.vacancy'))
    
    return render_template('shop_admin/vacancy.html', shop=shop)


@shop_admin_bp.route('/edit', methods=['GET', 'POST'])
@login_required
@owner_required
def edit():
    """Edit shop information."""
    shop = g.current_shop
    
    if request.method == 'POST':
        old_values = {
            'name': shop.name,
            'area': shop.area,
            'phone': shop.phone,
        }
        
        shop.name = request.form.get('name', '').strip() or shop.name
        shop.area = request.form.get('area', '') or shop.area
        shop.phone = request.form.get('phone', '').strip()
        shop.address = request.form.get('address', '').strip()
        shop.business_hours = request.form.get('business_hours', '').strip()
        shop.price_range = request.form.get('price_range', '').strip()
        shop.description = request.form.get('description', '').strip()
        # カテゴリは管理者のみ変更可能（店舗側では変更不可）
        # shop.category = request.form.get('category', '')
        shop.tags = request.form.get('tags', '').strip()
        shop.is_published = request.form.get('is_published') == 'on'
        shop.is_featured = request.form.get('is_featured') == 'on'
        
        # Price range for search
        try:
            price_min = request.form.get('price_min', '').strip()
            shop.price_min = int(price_min) if price_min else None
        except ValueError:
            shop.price_min = None
        
        try:
            price_max = request.form.get('price_max', '').strip()
            shop.price_max = int(price_max) if price_max else None
        except ValueError:
            shop.price_max = None
        
        db.session.commit()
        
        audit_log(AuditLog.ACTION_SHOP_EDIT, 'shop', shop.id,
                 old_value=old_values,
                 new_value={'name': shop.name, 'area': shop.area, 'phone': shop.phone})
        
        flash('店舗情報を更新しました。', 'success')
        return redirect(url_for('shop_admin.edit'))
    
    return render_template('shop_admin/edit.html', 
                          shop=shop, 
                          areas=Shop.AREAS,
                          categories=Shop.CATEGORIES,
                          category_labels=Shop.CATEGORY_LABELS)


@shop_admin_bp.route('/jobs', methods=['GET', 'POST'])
@login_required
@owner_required
def jobs():
    """Job posting management."""
    shop = g.current_shop
    
    # Get or create job
    job = shop.jobs.first()
    if not job:
        job = Job(shop_id=shop.id)
        db.session.add(job)
        db.session.commit()
    
    if request.method == 'POST':
        old_active = job.is_active
        
        job.is_active = request.form.get('is_active') == 'on'
        job.hourly_wage = request.form.get('hourly_wage', '').strip()
        job.benefits = request.form.get('benefits', '').strip()
        job.trial_available = request.form.get('trial_available') == 'on'
        
        expires_at_str = request.form.get('expires_at', '')
        if expires_at_str:
            try:
                job.expires_at = datetime.strptime(expires_at_str, '%Y-%m-%d').date()
            except ValueError:
                flash('掲載期限の形式が不正です。', 'danger')
                return redirect(url_for('shop_admin.jobs'))
        else:
            job.expires_at = None
        
        db.session.commit()
        
        audit_log(AuditLog.ACTION_JOB_UPDATE, 'job', job.id,
                 old_value={'is_active': old_active},
                 new_value={'is_active': job.is_active})
        
        flash('求人情報を更新しました。', 'success')
        return redirect(url_for('shop_admin.jobs'))
    
    return render_template('shop_admin/jobs.html', shop=shop, job=job)


@shop_admin_bp.route('/billing')
@login_required
@owner_required
def billing():
    """View billing status."""
    shop = g.current_shop
    subscription = shop.subscription
    
    billing_events = shop.billing_events.order_by(
        db.desc('created_at')
    ).limit(20).all()
    
    return render_template('shop_admin/billing.html',
                          shop=shop,
                          subscription=subscription,
                          billing_events=billing_events)


# ============================================
# Shop QR Code
# ============================================

@shop_admin_bp.route('/qrcode')
@login_required
@shop_access_required
def shop_qrcode():
    """店舗専用QRコード発行ページ"""
    shop = g.current_shop
    
    # 店舗詳細ページのURL
    shop_url = url_for('public.shop_detail', shop_id=shop.id, _external=True)
    
    # QRコード生成（高解像度）
    qr_png_base64 = generate_qrcode_base64(shop_url, size=15)
    qr_png_high_res = generate_qrcode_base64(shop_url, size=25)  # 印刷用高解像度
    qr_svg = generate_qrcode_svg(shop_url)
    
    return render_template('shop_admin/qrcode.html',
                          shop=shop,
                          shop_url=shop_url,
                          qr_png_base64=qr_png_base64,
                          qr_png_high_res=qr_png_high_res,
                          qr_svg=qr_svg)


@shop_admin_bp.route('/select-shop/<int:shop_id>')
@login_required
def select_shop(shop_id):
    """Admin: Select shop to manage."""
    if not current_user.is_admin:
        flash('この操作は管理者のみ可能です。', 'danger')
        return redirect(url_for('shop_admin.dashboard'))
    
    shop = Shop.query.get_or_404(shop_id)
    session['admin_shop_id'] = shop.id
    
    flash(f'店舗「{shop.name}」を選択しました。', 'success')
    return redirect(url_for('shop_admin.dashboard'))


# ============================================
# Image Management
# ============================================

@shop_admin_bp.route('/images')
@login_required
@owner_required
def images():
    """Image management page."""
    shop = g.current_shop
    shop_images = shop.all_images
    return render_template('shop_admin/images.html', shop=shop, images=shop_images)


@shop_admin_bp.route('/images/upload', methods=['POST'])
@login_required
@owner_required
def upload_image():
    """Upload shop image with auto-resize."""
    from ..utils.helpers import validate_image_file
    
    shop = g.current_shop
    
    if 'image' not in request.files:
        flash('画像が選択されていません。', 'danger')
        return redirect(url_for('shop_admin.images'))
    
    file = request.files['image']
    
    # Validate image file (extension, MIME type, content)
    is_valid, error_message = validate_image_file(file)
    if not is_valid:
        flash(error_message, 'danger')
        return redirect(url_for('shop_admin.images'))
    
    # 画像を自動リサイズ＆クラウドアップロード
    try:
        optimized_data, fmt = resize_and_optimize_image(file)
        if optimized_data:
            result = cloud_upload(optimized_data, 'shops', filename_prefix=f"{shop.id}_")
            filename = result['filename'] if result else None
        else:
            filename = save_shop_image(file, shop.id)
    except Exception as e:
        current_app.logger.error(f"Image upload failed: {e}")
        filename = save_shop_image(file, shop.id)
    
    if not filename:
        flash('画像のアップロードに失敗しました。', 'danger')
        return redirect(url_for('shop_admin.images'))
    
    # Get max sort order
    max_order = db.session.query(db.func.max(ShopImage.sort_order)).filter_by(shop_id=shop.id).scalar() or 0
    
    # Set as main if it's the first image
    is_first = shop.images.count() == 0
    
    image = ShopImage(
        shop_id=shop.id,
        filename=filename,
        original_filename=secure_filename(file.filename),
        is_main=is_first,
        sort_order=max_order + 1
    )
    db.session.add(image)
    db.session.commit()
    
    flash('画像をアップロードしました（自動最適化済み）。', 'success')
    return redirect(url_for('shop_admin.images'))


@shop_admin_bp.route('/images/<int:image_id>/delete', methods=['POST'])
@login_required
@owner_required
def delete_image(image_id):
    """Delete shop image."""
    shop = g.current_shop
    
    image = ShopImage.query.filter_by(id=image_id, shop_id=shop.id).first_or_404()
    
    # Delete file (cloud or local)
    try:
        cloud_delete(image.filename, 'shops')
    except Exception as e:
        current_app.logger.error(f"Failed to delete image file: {e}")
    
    was_main = image.is_main
    
    db.session.delete(image)
    db.session.commit()
    
    # If deleted image was main, set first remaining as main
    if was_main:
        first_image = shop.images.first()
        if first_image:
            first_image.is_main = True
            db.session.commit()
    
    flash('画像を削除しました。', 'success')
    return redirect(url_for('shop_admin.images'))


@shop_admin_bp.route('/images/<int:image_id>/set-main', methods=['POST'])
@login_required
@owner_required
def set_main_image(image_id):
    """Set image as main."""
    shop = g.current_shop
    
    image = ShopImage.query.filter_by(id=image_id, shop_id=shop.id).first_or_404()
    
    # Unset all other main images
    ShopImage.query.filter_by(shop_id=shop.id, is_main=True).update({'is_main': False})
    
    # Set this as main
    image.is_main = True
    db.session.commit()
    
    flash('メイン画像を設定しました。', 'success')
    return redirect(url_for('shop_admin.images'))


@shop_admin_bp.route('/images/reorder', methods=['POST'])
@login_required
@owner_required
def reorder_images():
    """Reorder images via AJAX."""
    shop = g.current_shop
    
    data = request.get_json()
    if not data or 'order' not in data:
        return jsonify({'error': 'Invalid data'}), 400
    
    order = data['order']  # List of image IDs in new order
    
    for idx, image_id in enumerate(order):
        image = ShopImage.query.filter_by(id=image_id, shop_id=shop.id).first()
        if image:
            image.sort_order = idx
    
    db.session.commit()
    
    return jsonify({'success': True})


# ============================================
# Cast Management
# ============================================

@shop_admin_bp.route('/casts')
@login_required
@shop_access_required
def casts():
    """Cast management page."""
    shop = g.current_shop
    cast_list = Cast.query.filter_by(shop_id=shop.id).order_by(Cast.sort_order, Cast.name).all()
    return render_template('shop_admin/casts.html', shop=shop, casts=cast_list)


@shop_admin_bp.route('/casts/new', methods=['GET', 'POST'])
@login_required
@shop_access_required
def new_cast():
    """Create new cast."""
    shop = g.current_shop
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        display_name = request.form.get('display_name', '').strip()
        profile = request.form.get('profile', '').strip()
        twitter_url = request.form.get('twitter_url', '').strip()
        instagram_url = request.form.get('instagram_url', '').strip()
        tiktok_url = request.form.get('tiktok_url', '').strip()
        is_accepting_gifts = request.form.get('is_accepting_gifts') == 'on'
        
        # 年齢
        try:
            age = int(request.form.get('age', '').strip()) if request.form.get('age', '').strip() else None
        except (ValueError, TypeError):
            age = None
        
        if not name:
            flash('名前を入力してください。', 'danger')
            return render_template('shop_admin/cast_form.html', shop=shop, cast=None,
                                   preset_tags=CastTag.PRESET_TAGS, tag_categories=CastTag.CATEGORIES,
                                   tag_category_labels=CastTag.CATEGORY_LABELS)
        
        if age is None:
            flash('年齢を入力してください。', 'danger')
            return render_template('shop_admin/cast_form.html', shop=shop, cast=None,
                                   preset_tags=CastTag.PRESET_TAGS, tag_categories=CastTag.CATEGORIES,
                                   tag_category_labels=CastTag.CATEGORY_LABELS)
        
        # Get max sort order
        max_order = db.session.query(db.func.max(Cast.sort_order)).filter_by(shop_id=shop.id).scalar() or 0
        
        cast = Cast(
            shop_id=shop.id,
            name=name,
            display_name=display_name or None,
            age=age,
            profile=profile,
            twitter_url=twitter_url or None,
            instagram_url=instagram_url or None,
            tiktok_url=tiktok_url or None,
            video_url=request.form.get('video_url', '').strip() or None,
            gift_appeal=request.form.get('gift_appeal', '').strip() or None,
            is_accepting_gifts=is_accepting_gifts,
            is_active=True,
            sort_order=max_order + 1
        )
        
        # Handle image upload (cloud or local)
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename:
                try:
                    optimized_data, fmt = resize_and_optimize_image(file)
                    if optimized_data:
                        result = cloud_upload(optimized_data, 'casts', filename_prefix=f"cast_{shop.id}_")
                        if result:
                            cast.image_filename = result['filename']
                    else:
                        filename = save_cast_image(file, shop.id)
                        if filename:
                            cast.image_filename = filename
                except Exception as e:
                    current_app.logger.error(f"Cast image upload failed: {e}")
                    filename = save_cast_image(file, shop.id)
                    if filename:
                        cast.image_filename = filename
        
        db.session.add(cast)
        db.session.flush()  # cast.idを確定
        
        # タグ処理
        for category in CastTag.CATEGORIES:
            tag_values = request.form.get(f'tags_{category}', '').strip()
            if tag_values:
                tag_names = [t.strip() for t in tag_values.split(',') if t.strip()]
                CastTag.set_tags(cast.id, category, tag_names)
        
        # 追加画像（ギャラリー）処理
        gallery_files = request.files.getlist('gallery_images')
        for idx, gfile in enumerate(gallery_files):
            if gfile and gfile.filename:
                try:
                    optimized_data, fmt = resize_and_optimize_image(gfile)
                    if optimized_data:
                        result = cloud_upload(optimized_data, 'casts', filename_prefix=f"cast_{shop.id}_g{idx}_")
                        if result:
                            img = CastImage(cast_id=cast.id, filename=result['filename'], sort_order=idx)
                            db.session.add(img)
                except Exception as e:
                    current_app.logger.error(f"Cast gallery image upload failed: {e}")
        
        # 誕生日処理
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
        
        audit_log(AuditLog.ACTION_CAST_CREATE if hasattr(AuditLog, 'ACTION_CAST_CREATE') else 'cast_create', 
                  'cast', cast.id, new_value={'name': name})
        
        flash(f'キャスト「{cast.name_display}」を登録しました。', 'success')
        return redirect(url_for('shop_admin.casts'))
    
    return render_template('shop_admin/cast_form.html', shop=shop, cast=None,
                           preset_tags=CastTag.PRESET_TAGS, tag_categories=CastTag.CATEGORIES,
                           tag_category_labels=CastTag.CATEGORY_LABELS)


@shop_admin_bp.route('/casts/<int:cast_id>/edit', methods=['GET', 'POST'])
@login_required
@shop_access_required
def edit_cast(cast_id):
    """Edit cast."""
    shop = g.current_shop
    cast = Cast.query.filter_by(id=cast_id, shop_id=shop.id).first_or_404()
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        
        if not name:
            flash('名前を入力してください。', 'danger')
            return render_template('shop_admin/cast_form.html', shop=shop, cast=cast,
                                   preset_tags=CastTag.PRESET_TAGS, tag_categories=CastTag.CATEGORIES,
                                   tag_category_labels=CastTag.CATEGORY_LABELS)
        
        cast.name = name
        cast.display_name = request.form.get('display_name', '').strip() or None
        cast.profile = request.form.get('profile', '').strip()
        cast.twitter_url = request.form.get('twitter_url', '').strip() or None
        cast.instagram_url = request.form.get('instagram_url', '').strip() or None
        cast.tiktok_url = request.form.get('tiktok_url', '').strip() or None
        cast.video_url = request.form.get('video_url', '').strip() or None
        cast.gift_appeal = request.form.get('gift_appeal', '').strip() or None
        cast.is_accepting_gifts = request.form.get('is_accepting_gifts') == 'on'
        cast.is_active = request.form.get('is_active') == 'on'
        cast.is_visible = request.form.get('is_visible') == 'on'
        cast.is_featured = request.form.get('is_featured') == 'on'
        
        # 年齢
        try:
            cast.age = int(request.form.get('age', '').strip()) if request.form.get('age', '').strip() else None
        except (ValueError, TypeError):
            pass
        
        # キャストログイン設定
        enable_cast_login = request.form.get('enable_cast_login') == 'on'
        cast_pin = request.form.get('cast_pin', '').strip()
        
        if enable_cast_login:
            # ログインコードが未発行なら発行
            if not cast.login_code:
                cast.generate_login_code()
            
            # PINが入力されていれば更新
            if cast_pin:
                if len(cast_pin) == 4 and cast_pin.isdigit():
                    cast.set_pin(cast_pin)
                else:
                    flash('PINは4桁の数字で入力してください。', 'warning')
            elif not cast.pin_hash:
                # 初回でPIN未設定の場合はエラー
                flash('キャストログインを有効にするにはPINを設定してください。', 'warning')
        else:
            # ログインを無効化（コードは残すがPINを削除）
            cast.pin_hash = None
        
        # ギフト目標設定
        try:
            monthly_gift_goal = int(request.form.get('monthly_gift_goal', 0) or 0)
            cast.monthly_gift_goal = max(0, monthly_gift_goal)
        except (ValueError, TypeError):
            cast.monthly_gift_goal = 0
        
        cast.monthly_gift_goal_message = request.form.get('monthly_gift_goal_message', '').strip() or None
        cast.show_gift_progress = request.form.get('show_gift_progress') == 'on'
        
        # Handle image upload with auto-resize (cloud or local)
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename:
                try:
                    optimized_data, fmt = resize_and_optimize_image(file)
                    if optimized_data:
                        result = cloud_upload(optimized_data, 'casts', filename_prefix=f"cast_{shop.id}_")
                        if result:
                            # 古い画像を削除
                            if cast.image_filename:
                                cloud_delete(cast.image_filename, 'casts')
                            cast.image_filename = result['filename']
                    else:
                        new_filename = save_cast_image(file, shop.id)
                        if new_filename:
                            if cast.image_filename:
                                cloud_delete(cast.image_filename, 'casts')
                            cast.image_filename = new_filename
                except Exception as e:
                    current_app.logger.error(f"Cast image upload failed: {e}")
                    new_filename = save_cast_image(file, shop.id)
                    if new_filename:
                        if cast.image_filename:
                            cloud_delete(cast.image_filename, 'casts')
                        cast.image_filename = new_filename
        
        # タグ処理
        for category in CastTag.CATEGORIES:
            tag_values = request.form.get(f'tags_{category}', '').strip()
            tag_names = [t.strip() for t in tag_values.split(',') if t.strip()] if tag_values else []
            CastTag.set_tags(cast.id, category, tag_names)
        
        # 追加画像（ギャラリー）処理
        gallery_files = request.files.getlist('gallery_images')
        existing_count = CastImage.query.filter_by(cast_id=cast.id).count()
        for idx, gfile in enumerate(gallery_files):
            if gfile and gfile.filename:
                try:
                    optimized_data, fmt = resize_and_optimize_image(gfile)
                    if optimized_data:
                        result = cloud_upload(optimized_data, 'casts', filename_prefix=f"cast_{shop.id}_g{existing_count + idx}_")
                        if result:
                            img = CastImage(cast_id=cast.id, filename=result['filename'], sort_order=existing_count + idx)
                            db.session.add(img)
                except Exception as e:
                    current_app.logger.error(f"Cast gallery image upload failed: {e}")
        
        # ギャラリー画像削除処理
        delete_image_ids = request.form.getlist('delete_gallery_image')
        for img_id in delete_image_ids:
            try:
                img = CastImage.query.get(int(img_id))
                if img and img.cast_id == cast.id:
                    cloud_delete(img.filename, 'casts')
                    db.session.delete(img)
            except (ValueError, Exception) as e:
                current_app.logger.error(f"Gallery image delete failed: {e}")
        
        # 誕生日処理（一括再設定）
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
        
        flash(f'キャスト「{cast.name_display}」を更新しました。', 'success')
        return redirect(url_for('shop_admin.casts'))
    
    # 既存タグを取得
    existing_tags = CastTag.get_tags_by_cast(cast.id) if cast else {}
    existing_birthdays = CastBirthday.get_birthdays(cast.id) if cast else []
    gallery = CastImage.get_gallery(cast.id) if cast else []
    
    return render_template('shop_admin/cast_form.html', shop=shop, cast=cast,
                           preset_tags=CastTag.PRESET_TAGS, tag_categories=CastTag.CATEGORIES,
                           tag_category_labels=CastTag.CATEGORY_LABELS,
                           existing_tags=existing_tags, existing_birthdays=existing_birthdays,
                           gallery=gallery)


@shop_admin_bp.route('/casts/<int:cast_id>/delete', methods=['POST'])
@login_required
@shop_access_required
def delete_cast(cast_id):
    """Delete cast."""
    shop = g.current_shop
    cast = Cast.query.filter_by(id=cast_id, shop_id=shop.id).first_or_404()
    
    cast_name = cast.name_display
    
    # Delete image (cloud or local)
    if cast.image_filename:
        try:
            cloud_delete(cast.image_filename, 'casts')
        except:
            pass
    
    db.session.delete(cast)
    db.session.commit()
    
    flash(f'キャスト「{cast_name}」を削除しました。', 'success')
    return redirect(url_for('shop_admin.casts'))


@shop_admin_bp.route('/casts/reorder', methods=['POST'])
@login_required
@shop_access_required
def reorder_casts():
    """Reorder casts via AJAX."""
    shop = g.current_shop
    
    data = request.get_json()
    if not data or 'order' not in data:
        return jsonify({'error': 'Invalid data'}), 400
    
    for idx, cast_id in enumerate(data['order']):
        cast = Cast.query.filter_by(id=cast_id, shop_id=shop.id).first()
        if cast:
            cast.sort_order = idx
    
    db.session.commit()
    
    return jsonify({'success': True})


# ============================================
# Gift Earnings
# ============================================

@shop_admin_bp.route('/earnings')
@login_required
@owner_required
def earnings():
    """View gift earnings."""
    shop = g.current_shop
    
    # Get shop's gift earnings
    page = request.args.get('page', 1, type=int)
    earnings_query = Earning.query.filter(
        Earning.shop_id == shop.id,
        Earning.earning_type.in_([Earning.TYPE_SHOP, Earning.TYPE_CAST])
    ).order_by(Earning.created_at.desc())
    
    earnings_paginated = earnings_query.paginate(page=page, per_page=50, error_out=False)
    
    # Summary
    shop_total = db.session.query(db.func.sum(Earning.amount)).filter(
        Earning.shop_id == shop.id,
        Earning.earning_type == Earning.TYPE_SHOP
    ).scalar() or 0
    
    cast_total = db.session.query(db.func.sum(Earning.amount)).filter(
        Earning.shop_id == shop.id,
        Earning.earning_type == Earning.TYPE_CAST
    ).scalar() or 0
    
    # Cast earnings breakdown
    cast_earnings = db.session.query(
        Cast.id, Cast.name, Cast.display_name,
        db.func.sum(Earning.amount).label('total')
    ).join(Earning, Cast.id == Earning.cast_id).filter(
        Cast.shop_id == shop.id,
        Earning.earning_type == Earning.TYPE_CAST
    ).group_by(Cast.id, Cast.name, Cast.display_name).all()
    
    return render_template('shop_admin/earnings.html',
                           shop=shop,
                           earnings=earnings_paginated,
                           shop_total=shop_total,
                           cast_total=cast_total,
                           cast_earnings=cast_earnings)


def save_cast_image(file, shop_id):
    """Save uploaded cast image and return filename (cloud or local)."""
    from ..utils.helpers import validate_image_file
    
    is_valid, error_message = validate_image_file(file)
    if not is_valid:
        return None
    
    file.seek(0)
    result = cloud_upload(file, 'casts', filename_prefix=f"cast_{shop_id}_")
    if result:
        return result['filename']
    return None


# ============================================
# Shift Management (出勤管理)
# ============================================

@shop_admin_bp.route('/shifts')
@login_required
@shop_access_required
def shifts():
    """出勤シフト管理ページ"""
    from ..models.cast_shift import CastShift
    from ..services.ad_service import AdService
    
    shop = g.current_shop
    
    # キャスト出勤表示権限があるか確認
    can_manage_shifts = AdService.can_show_cast_shift(shop.id)
    
    if not can_manage_shifts:
        flash('この機能を利用するには有料プランへのアップグレードが必要です。', 'warning')
        return redirect(url_for('shop_admin.dashboard'))
    
    # 今週のシフトを取得
    today = date.today()
    start_of_week = today - timedelta(days=today.weekday())
    
    week_shifts = CastShift.get_week_shifts(shop.id, start_of_week)
    
    # キャスト一覧
    casts = Cast.get_active_by_shop(shop.id)
    
    # 日付リスト（今週）
    dates = [start_of_week + timedelta(days=i) for i in range(7)]
    
    # シフトをキャスト×日付のマトリックスに整理
    shift_matrix = {}
    for cast in casts:
        shift_matrix[cast.id] = {}
        for d in dates:
            shift_matrix[cast.id][d] = None
    
    for shift in week_shifts:
        if shift.cast_id in shift_matrix:
            shift_matrix[shift.cast_id][shift.shift_date] = shift
    
    return render_template('shop_admin/shifts.html',
                          shop=shop,
                          casts=casts,
                          dates=dates,
                          shift_matrix=shift_matrix,
                          today=today,
                          can_manage_shifts=can_manage_shifts)


@shop_admin_bp.route('/shifts/update', methods=['POST'])
@login_required
@shop_access_required
def update_shift():
    """シフトを更新（AJAX）"""
    from ..models.cast_shift import CastShift
    from ..services.ad_service import AdService
    
    shop = g.current_shop
    
    # 権限確認
    if not AdService.can_show_cast_shift(shop.id):
        return jsonify({'error': '権限がありません'}), 403
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'データが不正です'}), 400
    
    cast_id = data.get('cast_id')
    shift_date_str = data.get('shift_date')
    start_time_str = data.get('start_time')
    end_time_str = data.get('end_time')
    status = data.get('status')
    
    # キャストが自店舗のものか確認
    cast = Cast.query.filter_by(id=cast_id, shop_id=shop.id).first()
    if not cast:
        return jsonify({'error': 'キャストが見つかりません'}), 404
    
    # 日付パース
    try:
        shift_date = datetime.strptime(shift_date_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return jsonify({'error': '日付形式が不正です'}), 400
    
    # 時間パース
    start_time = None
    end_time = None
    if start_time_str:
        try:
            start_time = datetime.strptime(start_time_str, '%H:%M').time()
        except ValueError:
            pass
    if end_time_str:
        try:
            end_time = datetime.strptime(end_time_str, '%H:%M').time()
        except ValueError:
            pass
    
    # シフト作成/更新
    shift = CastShift.create_or_update(
        cast_id=cast_id,
        shop_id=shop.id,
        shift_date=shift_date,
        start_time=start_time,
        end_time=end_time,
        status=status or CastShift.STATUS_SCHEDULED,
        user_id=current_user.id
    )
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'shift_id': shift.id,
        'status': shift.status,
        'time_display': shift.time_display
    })


@shop_admin_bp.route('/shifts/<int:shift_id>/start', methods=['POST'])
@login_required
@shop_access_required
def start_shift(shift_id):
    """出勤開始"""
    from ..models.cast_shift import CastShift
    
    shop = g.current_shop
    
    shift = CastShift.query.filter_by(id=shift_id, shop_id=shop.id).first_or_404()
    shift.start_working()
    db.session.commit()
    
    flash(f'{shift.cast.name_display}さんの出勤を開始しました。', 'success')
    return redirect(url_for('shop_admin.shifts'))


@shop_admin_bp.route('/shifts/<int:shift_id>/finish', methods=['POST'])
@login_required
@shop_access_required
def finish_shift(shift_id):
    """退勤"""
    from ..models.cast_shift import CastShift
    
    shop = g.current_shop
    
    shift = CastShift.query.filter_by(id=shift_id, shop_id=shop.id).first_or_404()
    shift.finish_working()
    db.session.commit()
    
    flash(f'{shift.cast.name_display}さんが退勤しました。', 'success')
    return redirect(url_for('shop_admin.shifts'))


@shop_admin_bp.route('/shifts/<int:shift_id>/cancel', methods=['POST'])
@login_required
@shop_access_required
def cancel_shift(shift_id):
    """シフトキャンセル"""
    from ..models.cast_shift import CastShift
    
    shop = g.current_shop
    
    shift = CastShift.query.filter_by(id=shift_id, shop_id=shop.id).first_or_404()
    reason = request.form.get('reason', '')
    shift.cancel(reason)
    db.session.commit()
    
    flash(f'{shift.cast.name_display}さんのシフトをキャンセルしました。', 'success')
    return redirect(url_for('shop_admin.shifts'))


# ============================================
# Store Plan Status (プラン状況)
# ============================================

@shop_admin_bp.route('/plan')
@login_required
@owner_required
def plan():
    """プラン状況ページ"""
    from ..models.store_plan import StorePlan
    from ..models.ad_entitlement import AdEntitlement
    from ..services.ad_service import AdService
    
    shop = g.current_shop
    
    # プラン取得（なければ無料プランを作成）
    store_plan = StorePlan.query.filter_by(shop_id=shop.id).first()
    if not store_plan:
        store_plan = StorePlan.get_or_create_free(shop.id)
        db.session.commit()
    
    # 現在有効な広告権利を取得
    entitlements = AdEntitlement.get_for_target(
        target_type='shop',
        target_id=shop.id,
        active_only=True
    )
    
    # バッジ情報
    badges = AdService.get_shop_badges(shop.id)
    
    return render_template('shop_admin/plan.html',
                          shop=shop,
                          store_plan=store_plan,
                          entitlements=entitlements,
                          badges=badges,
                          plan_labels=StorePlan.PLAN_LABELS,
                          plan_prices=StorePlan.PLAN_PRICES,
                          plan_features=StorePlan.PLAN_FEATURES)


# ============================================
# 店舗ポイントカード管理
# ============================================

@shop_admin_bp.route('/point-card')
@login_required
@owner_required
def point_card():
    """ポイントカード設定ページ"""
    from ..models.shop_point import ShopPointCard, CustomerShopPoint
    
    shop = g.current_shop
    
    # ポイントカード設定を取得（なければ作成）
    card_config = ShopPointCard.get_or_create(shop.id)
    db.session.commit()
    
    # 最近の来店者
    recent_visitors = CustomerShopPoint.query.filter_by(
        shop_id=shop.id
    ).order_by(CustomerShopPoint.last_visit_at.desc()).limit(20).all()
    
    # ランキング
    top_customers = CustomerShopPoint.query.filter_by(
        shop_id=shop.id
    ).order_by(CustomerShopPoint.total_earned.desc()).limit(10).all()
    
    return render_template('shop_admin/point_card.html',
                          shop=shop,
                          card_config=card_config,
                          recent_visitors=recent_visitors,
                          top_customers=top_customers)


@shop_admin_bp.route('/point-card/settings', methods=['POST'])
@login_required
@owner_required
def point_card_settings():
    """ポイントカード設定を更新"""
    from ..models.shop_point import ShopPointCard
    
    shop = g.current_shop
    
    card_config = ShopPointCard.get_or_create(shop.id)
    
    card_config.is_active = request.form.get('is_active') == 'on'
    card_config.card_name = request.form.get('card_name', 'ポイントカード').strip() or 'ポイントカード'
    
    try:
        card_config.visit_points = max(1, int(request.form.get('visit_points', 100)))
    except (ValueError, TypeError):
        card_config.visit_points = 100
    
    try:
        card_config.min_visit_interval_hours = max(0, int(request.form.get('min_visit_interval_hours', 4)))
    except (ValueError, TypeError):
        card_config.min_visit_interval_hours = 4
    
    try:
        card_config.reward_threshold = max(0, int(request.form.get('reward_threshold', 1000)))
    except (ValueError, TypeError):
        card_config.reward_threshold = 1000
    
    card_config.reward_description = request.form.get('reward_description', '').strip() or None
    card_config.card_color = request.form.get('card_color', '#6366f1').strip() or '#6366f1'
    
    db.session.commit()
    
    flash('ポイントカード設定を更新しました。', 'success')
    return redirect(url_for('shop_admin.point_card'))


@shop_admin_bp.route('/point-card/grant', methods=['POST'])
@login_required
@shop_access_required
def grant_visit_points():
    """来店ポイントを付与"""
    from ..services.shop_point_service import ShopPointService
    from ..models import Customer
    
    shop = g.current_shop
    
    # 顧客を検索（メールで）
    email = request.form.get('customer_email', '').strip().lower()
    
    if not email:
        flash('メールアドレスを入力してください。', 'danger')
        return redirect(url_for('shop_admin.point_card'))
    
    customer = Customer.query.filter_by(email=email).first()
    
    if not customer:
        flash('お客様が見つかりません。', 'danger')
        return redirect(url_for('shop_admin.point_card'))
    
    # ポイント付与
    success, message, points = ShopPointService.grant_visit_points(
        customer_id=customer.id,
        shop_id=shop.id,
        verified_by=current_user.id,
        method='manual'
    )
    
    if success:
        flash(f'{customer.nickname or customer.email}さんに{message}', 'success')
    else:
        flash(message, 'warning')
    
    return redirect(url_for('shop_admin.point_card'))


# ============================================
# ランク制度管理
# ============================================

@shop_admin_bp.route('/point-card/ranks')
@login_required
@owner_required
def point_card_ranks():
    """ランク制度設定ページ"""
    from ..models.shop_point import ShopPointCard
    from ..models.shop_point_rank import ShopPointRank
    
    shop = g.current_shop
    card_config = ShopPointCard.get_or_create(shop.id)
    db.session.commit()
    
    ranks = ShopPointRank.get_ranks_by_shop(shop.id)
    
    return render_template('shop_admin/point_card_ranks.html',
                          shop=shop,
                          card_config=card_config,
                          ranks=ranks)


@shop_admin_bp.route('/point-card/ranks/toggle', methods=['POST'])
@login_required
@owner_required
def toggle_rank_system():
    """ランク制度のON/OFF切替"""
    from ..models.shop_point import ShopPointCard
    from ..models.shop_point_rank import ShopPointRank
    
    shop = g.current_shop
    card_config = ShopPointCard.get_or_create(shop.id)
    
    card_config.rank_system_enabled = not card_config.rank_system_enabled
    
    # 有効にした時にランクが0件ならデフォルトランクを作成
    if card_config.rank_system_enabled:
        existing = ShopPointRank.query.filter_by(shop_id=shop.id).count()
        if existing == 0:
            ShopPointRank.create_default_ranks(shop.id)
    
    db.session.commit()
    
    status = '有効' if card_config.rank_system_enabled else '無効'
    flash(f'ランク制度を{status}にしました。', 'success')
    return redirect(url_for('shop_admin.point_card_ranks'))


@shop_admin_bp.route('/point-card/ranks/save', methods=['POST'])
@login_required
@owner_required
def save_ranks():
    """ランク一覧を一括保存"""
    from ..models.shop_point_rank import ShopPointRank
    
    shop = g.current_shop
    
    # フォームからランクデータを取得
    rank_ids = request.form.getlist('rank_id[]')
    rank_names = request.form.getlist('rank_name[]')
    rank_levels = request.form.getlist('rank_level[]')
    min_points_list = request.form.getlist('min_total_points[]')
    multipliers = request.form.getlist('point_multiplier[]')
    colors = request.form.getlist('rank_color[]')
    icons = request.form.getlist('rank_icon[]')
    descriptions = request.form.getlist('bonus_description[]')
    
    # 削除対象
    delete_ids = request.form.getlist('delete_rank_id[]')
    if delete_ids:
        ShopPointRank.query.filter(
            ShopPointRank.id.in_([int(d) for d in delete_ids if d]),
            ShopPointRank.shop_id == shop.id
        ).delete(synchronize_session=False)
    
    # 保存
    for i in range(len(rank_names)):
        name = rank_names[i].strip()
        if not name:
            continue
        
        try:
            level = int(rank_levels[i]) if i < len(rank_levels) else i + 1
            min_pts = int(min_points_list[i]) if i < len(min_points_list) else 0
            mult = float(multipliers[i]) if i < len(multipliers) else 1.0
        except (ValueError, IndexError):
            continue
        
        color = colors[i].strip() if i < len(colors) else '#6366f1'
        icon = icons[i].strip() if i < len(icons) else '⭐'
        desc = descriptions[i].strip() if i < len(descriptions) else ''
        
        rid = rank_ids[i] if i < len(rank_ids) else ''
        
        if rid and rid.isdigit():
            # 既存ランク更新
            rank = ShopPointRank.query.filter_by(id=int(rid), shop_id=shop.id).first()
            if rank:
                rank.rank_name = name
                rank.rank_level = level
                rank.min_total_points = min_pts
                rank.point_multiplier = mult
                rank.rank_color = color
                rank.rank_icon = icon
                rank.bonus_description = desc
        else:
            # 新規ランク
            rank = ShopPointRank(
                shop_id=shop.id,
                rank_name=name,
                rank_level=level,
                min_total_points=min_pts,
                point_multiplier=mult,
                rank_color=color,
                rank_icon=icon,
                bonus_description=desc
            )
            db.session.add(rank)
    
    db.session.commit()
    flash('ランク設定を保存しました。', 'success')
    return redirect(url_for('shop_admin.point_card_ranks'))


@shop_admin_bp.route('/point-card/ranks/reset-defaults', methods=['POST'])
@login_required
@owner_required
def reset_default_ranks():
    """デフォルトランクにリセット"""
    from ..models.shop_point_rank import ShopPointRank
    
    shop = g.current_shop
    
    # 既存削除
    ShopPointRank.query.filter_by(shop_id=shop.id).delete(synchronize_session=False)
    # デフォルト作成
    ShopPointRank.create_default_ranks(shop.id)
    
    db.session.commit()
    flash('ランクをデフォルトにリセットしました。', 'success')
    return redirect(url_for('shop_admin.point_card_ranks'))


@shop_admin_bp.route('/plan/subscribe', methods=['POST'])
@login_required
@owner_required
def subscribe_plan():
    """有料プランに申し込み（Stripe Checkout）"""
    import stripe
    from ..models.store_plan import StorePlan, StorePlanHistory
    
    shop = g.current_shop
    plan_type = request.form.get('plan_type')
    
    if plan_type not in [StorePlan.PLAN_STANDARD, StorePlan.PLAN_PREMIUM]:
        flash('無効なプランです。', 'danger')
        return redirect(url_for('shop_admin.plan'))
    
    # Stripe設定確認
    stripe_secret_key = current_app.config.get('STRIPE_SECRET_KEY')
    if not stripe_secret_key:
        flash('決済システムが設定されていません。管理者にお問い合わせください。', 'danger')
        return redirect(url_for('shop_admin.plan'))
    
    stripe.api_key = stripe_secret_key
    
    # プラン情報
    plan_prices = StorePlan.PLAN_PRICES
    plan_labels = StorePlan.PLAN_LABELS
    price = plan_prices.get(plan_type, 0)
    plan_name = plan_labels.get(plan_type, plan_type)
    
    try:
        # Stripe Checkout Session作成
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'jpy',
                    'product_data': {
                        'name': f'Night-Walk {plan_name}',
                        'description': f'店舗: {shop.name}',
                    },
                    'unit_amount': price,
                    'recurring': {
                        'interval': 'month',
                    },
                },
                'quantity': 1,
            }],
            mode='subscription',
            success_url=url_for('shop_admin.plan_success', _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=url_for('shop_admin.plan', _external=True),
            metadata={
                'shop_id': str(shop.id),
                'plan_type': plan_type,
                'user_id': str(current_user.id),
            },
            customer_email=current_user.email,
        )
        
        # 監査ログ
        audit_log('plan_checkout_started', 'shop', shop.id,
                  new_value={'plan_type': plan_type, 'session_id': checkout_session.id})
        
        return redirect(checkout_session.url)
        
    except stripe.error.StripeError as e:
        current_app.logger.error(f"Stripe error: {e}")
        flash('決済処理中にエラーが発生しました。しばらく経ってから再度お試しください。', 'danger')
        return redirect(url_for('shop_admin.plan'))


@shop_admin_bp.route('/plan/success')
@login_required
@owner_required
def plan_success():
    """プラン申し込み成功"""
    import stripe
    from ..models.store_plan import StorePlan, StorePlanHistory
    
    shop = g.current_shop
    session_id = request.args.get('session_id')
    
    if not session_id:
        flash('セッション情報がありません。', 'danger')
        return redirect(url_for('shop_admin.plan'))
    
    stripe_secret_key = current_app.config.get('STRIPE_SECRET_KEY')
    if not stripe_secret_key:
        flash('決済システムエラー', 'danger')
        return redirect(url_for('shop_admin.plan'))
    
    stripe.api_key = stripe_secret_key
    
    try:
        # Checkout Sessionを取得
        checkout_session = stripe.checkout.Session.retrieve(session_id)
        
        # メタデータから情報を取得
        shop_id = int(checkout_session.metadata.get('shop_id', 0))
        plan_type = checkout_session.metadata.get('plan_type')
        
        # 店舗IDの確認
        if shop_id != shop.id:
            flash('不正なアクセスです。', 'danger')
            return redirect(url_for('shop_admin.plan'))
        
        # 支払い完了確認
        if checkout_session.payment_status != 'paid':
            flash('お支払いが完了していません。', 'warning')
            return redirect(url_for('shop_admin.plan'))
        
        # プランを更新
        store_plan = StorePlan.query.filter_by(shop_id=shop.id).first()
        if not store_plan:
            store_plan = StorePlan(shop_id=shop.id)
            db.session.add(store_plan)
        
        old_plan = store_plan.plan_type
        store_plan.plan_type = plan_type
        store_plan.status = StorePlan.STATUS_ACTIVE
        store_plan.stripe_subscription_id = checkout_session.subscription
        store_plan.stripe_customer_id = checkout_session.customer
        store_plan.starts_at = datetime.utcnow()
        
        # 履歴を記録
        StorePlanHistory.log(
            shop_id=shop.id,
            action='upgraded',
            plan_id=store_plan.id,
            from_plan=old_plan,
            to_plan=plan_type,
            amount=StorePlan.PLAN_PRICES.get(plan_type, 0),
            user_id=current_user.id,
            note=f'Stripe Session: {session_id}'
        )
        
        # 広告権利を同期
        store_plan.sync_entitlements(current_user.id)
        
        db.session.commit()
        
        # 監査ログ
        audit_log('plan_upgraded', 'shop', shop.id,
                  old_value={'plan': old_plan},
                  new_value={'plan': plan_type})
        
        flash(f'「{StorePlan.PLAN_LABELS.get(plan_type)}」プランへの申し込みが完了しました！', 'success')
        
    except stripe.error.StripeError as e:
        current_app.logger.error(f"Stripe error on success: {e}")
        flash('プラン情報の確認中にエラーが発生しました。', 'danger')
    
    return redirect(url_for('shop_admin.plan'))


@shop_admin_bp.route('/plan/cancel', methods=['POST'])
@login_required
@owner_required
def cancel_plan():
    """プランを解約"""
    import stripe
    from ..models.store_plan import StorePlan, StorePlanHistory
    
    shop = g.current_shop
    
    store_plan = StorePlan.query.filter_by(shop_id=shop.id).first()
    if not store_plan or store_plan.plan_type == StorePlan.PLAN_FREE:
        flash('解約するプランがありません。', 'warning')
        return redirect(url_for('shop_admin.plan'))
    
    # Stripeのサブスクリプションをキャンセル
    if store_plan.stripe_subscription_id:
        stripe_secret_key = current_app.config.get('STRIPE_SECRET_KEY')
        if stripe_secret_key:
            stripe.api_key = stripe_secret_key
            try:
                # 期間終了時にキャンセル（即時キャンセルではない）
                stripe.Subscription.modify(
                    store_plan.stripe_subscription_id,
                    cancel_at_period_end=True
                )
            except stripe.error.StripeError as e:
                current_app.logger.error(f"Stripe cancel error: {e}")
    
    old_plan = store_plan.plan_type
    
    # 履歴を記録
    StorePlanHistory.log(
        shop_id=shop.id,
        action='canceled',
        plan_id=store_plan.id,
        from_plan=old_plan,
        to_plan=StorePlan.PLAN_FREE,
        user_id=current_user.id,
        note='ユーザーによる解約'
    )
    
    # プランをキャンセル状態に
    store_plan.cancel(current_user.id, reason='ユーザーによる解約')
    
    db.session.commit()
    
    # 監査ログ
    audit_log('plan_canceled', 'shop', shop.id,
              old_value={'plan': old_plan},
              new_value={'plan': 'canceled'})
    
    flash('プランの解約を受け付けました。現在の契約期間終了後、無料プランに移行します。', 'info')
    return redirect(url_for('shop_admin.plan'))


# ==================== 紹介制度 ====================

@shop_admin_bp.route('/referral')
@login_required
@shop_access_required
def referral():
    """紹介制度管理ページ"""
    from ..models.referral import ShopReferral
    
    shop = g.current_shop
    
    # 紹介統計
    stats = ShopReferral.get_shop_referral_stats(shop.id)
    
    # 有効な紹介コード一覧
    active_codes = ShopReferral.get_active_codes(shop.id)
    
    # 使用済み紹介一覧
    used_referrals = ShopReferral.query.filter(
        ShopReferral.referrer_shop_id == shop.id,
        ShopReferral.status.in_([ShopReferral.STATUS_USED, ShopReferral.STATUS_REWARDED])
    ).order_by(ShopReferral.used_at.desc()).limit(20).all()
    
    return render_template('shop_admin/referral.html',
                           shop=shop,
                           stats=stats,
                           active_codes=active_codes,
                           used_referrals=used_referrals,
                           max_free_months=ShopReferral.MAX_FREE_MONTHS)


@shop_admin_bp.route('/referral/create', methods=['POST'])
@login_required
@shop_access_required
@limiter.limit("10 per hour")
def create_referral_code():
    """紹介コードを発行"""
    from ..models.referral import ShopReferral
    
    shop = g.current_shop
    
    # 紹介統計をチェック（最大特典に達している場合も発行は可能）
    stats = ShopReferral.get_shop_referral_stats(shop.id)
    
    # 新しいコードを発行
    referral = ShopReferral.create_for_shop(shop.id, expires_days=30)
    db.session.commit()
    
    audit_log('referral_code_created', 'shop', shop.id,
              new_value={'code': referral.referral_code})
    
    flash(f'紹介コードを発行しました: {referral.referral_code}', 'success')
    return redirect(url_for('shop_admin.referral'))


@shop_admin_bp.route('/referral/use', methods=['POST'])
@login_required
@shop_access_required
@limiter.limit("5 per hour")
def use_referral_code():
    """紹介コードを使用（自店舗が紹介を受ける）"""
    from ..models.referral import ShopReferral
    
    shop = g.current_shop
    code = request.form.get('code', '').strip().upper()
    
    if not code:
        flash('紹介コードを入力してください。', 'danger')
        return redirect(url_for('shop_admin.referral'))
    
    success, referral, error = ShopReferral.use_code(code, shop.id)
    
    if not success:
        flash(error, 'danger')
        return redirect(url_for('shop_admin.referral'))
    
    db.session.commit()
    
    # 紹介元に特典を付与
    success, months, error = referral.grant_reward()
    if success:
        db.session.commit()
        flash(f'紹介コードを使用しました！紹介元に{months}ヶ月の無料延長が付与されました。', 'success')
    else:
        flash(f'紹介コードを使用しましたが、特典付与に失敗しました: {error}', 'warning')
    
    audit_log('referral_code_used', 'shop', shop.id,
              new_value={'code': code, 'referrer_shop_id': referral.referrer_shop_id})
    
    return redirect(url_for('shop_admin.referral'))
