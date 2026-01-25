"""
Night-Walk MVP - Shop Admin Routes (店舗管理)
"""
import os
import uuid
from datetime import datetime, date
from flask import Blueprint, render_template, redirect, url_for, flash, request, g, session, current_app, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from ..extensions import db
from ..models.shop import Shop, VacancyStatus, VacancyHistory, ShopImage
from ..models.job import Job
from ..models.booking import BookingLog
from ..models.billing import Subscription
from ..models.audit import AuditLog
from ..models.gift import Cast, GiftTransaction
from ..models.earning import Earning
from ..utils.decorators import shop_access_required, owner_required
from ..utils.logger import audit_log
from ..utils.helpers import get_client_ip

shop_admin_bp = Blueprint('shop_admin', __name__)

# Allowed image extensions
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    """Check if file extension is allowed."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_shop_image(file, shop_id):
    """Save uploaded image and return filename."""
    if not file or not allowed_file(file.filename):
        return None
    
    # Create unique filename
    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = f"{shop_id}_{uuid.uuid4().hex[:8]}.{ext}"
    
    # Ensure upload directory exists
    upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'shops')
    os.makedirs(upload_dir, exist_ok=True)
    
    # Save file
    filepath = os.path.join(upload_dir, filename)
    file.save(filepath)
    
    return filename


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
        shop.category = request.form.get('category', '')
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
    """Upload shop image."""
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
    
    flash('画像をアップロードしました。', 'success')
    return redirect(url_for('shop_admin.images'))


@shop_admin_bp.route('/images/<int:image_id>/delete', methods=['POST'])
@login_required
@owner_required
def delete_image(image_id):
    """Delete shop image."""
    shop = g.current_shop
    
    image = ShopImage.query.filter_by(id=image_id, shop_id=shop.id).first_or_404()
    
    # Delete file
    try:
        filepath = os.path.join(current_app.root_path, 'static', 'uploads', 'shops', image.filename)
        if os.path.exists(filepath):
            os.remove(filepath)
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
@owner_required
def casts():
    """Cast management page."""
    shop = g.current_shop
    cast_list = Cast.query.filter_by(shop_id=shop.id).order_by(Cast.sort_order, Cast.name).all()
    return render_template('shop_admin/casts.html', shop=shop, casts=cast_list)


@shop_admin_bp.route('/casts/new', methods=['GET', 'POST'])
@login_required
@owner_required
def new_cast():
    """Create new cast."""
    shop = g.current_shop
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        display_name = request.form.get('display_name', '').strip()
        profile = request.form.get('profile', '').strip()
        twitter_url = request.form.get('twitter_url', '').strip()
        instagram_url = request.form.get('instagram_url', '').strip()
        is_accepting_gifts = request.form.get('is_accepting_gifts') == 'on'
        
        if not name:
            flash('名前を入力してください。', 'danger')
            return render_template('shop_admin/cast_form.html', shop=shop, cast=None)
        
        # Get max sort order
        max_order = db.session.query(db.func.max(Cast.sort_order)).filter_by(shop_id=shop.id).scalar() or 0
        
        cast = Cast(
            shop_id=shop.id,
            name=name,
            display_name=display_name or None,
            profile=profile,
            twitter_url=twitter_url or None,
            instagram_url=instagram_url or None,
            is_accepting_gifts=is_accepting_gifts,
            is_active=True,
            sort_order=max_order + 1
        )
        
        # Handle image upload
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename:
                filename = save_cast_image(file, shop.id)
                if filename:
                    cast.image_filename = filename
        
        db.session.add(cast)
        db.session.commit()
        
        audit_log(AuditLog.ACTION_CAST_CREATE if hasattr(AuditLog, 'ACTION_CAST_CREATE') else 'cast_create', 
                  'cast', cast.id, new_value={'name': name})
        
        flash(f'キャスト「{cast.name_display}」を登録しました。', 'success')
        return redirect(url_for('shop_admin.casts'))
    
    return render_template('shop_admin/cast_form.html', shop=shop, cast=None)


@shop_admin_bp.route('/casts/<int:cast_id>/edit', methods=['GET', 'POST'])
@login_required
@owner_required
def edit_cast(cast_id):
    """Edit cast."""
    shop = g.current_shop
    cast = Cast.query.filter_by(id=cast_id, shop_id=shop.id).first_or_404()
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        
        if not name:
            flash('名前を入力してください。', 'danger')
            return render_template('shop_admin/cast_form.html', shop=shop, cast=cast)
        
        cast.name = name
        cast.display_name = request.form.get('display_name', '').strip() or None
        cast.profile = request.form.get('profile', '').strip()
        cast.twitter_url = request.form.get('twitter_url', '').strip() or None
        cast.instagram_url = request.form.get('instagram_url', '').strip() or None
        cast.is_accepting_gifts = request.form.get('is_accepting_gifts') == 'on'
        cast.is_active = request.form.get('is_active') == 'on'
        cast.is_featured = request.form.get('is_featured') == 'on'
        
        # Handle image upload
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename:
                filename = save_cast_image(file, shop.id)
                if filename:
                    # Delete old image
                    if cast.image_filename:
                        try:
                            old_path = os.path.join(current_app.root_path, 'static', 'uploads', 'casts', cast.image_filename)
                            if os.path.exists(old_path):
                                os.remove(old_path)
                        except:
                            pass
                    cast.image_filename = filename
        
        db.session.commit()
        
        flash(f'キャスト「{cast.name_display}」を更新しました。', 'success')
        return redirect(url_for('shop_admin.casts'))
    
    return render_template('shop_admin/cast_form.html', shop=shop, cast=cast)


@shop_admin_bp.route('/casts/<int:cast_id>/delete', methods=['POST'])
@login_required
@owner_required
def delete_cast(cast_id):
    """Delete cast."""
    shop = g.current_shop
    cast = Cast.query.filter_by(id=cast_id, shop_id=shop.id).first_or_404()
    
    cast_name = cast.name_display
    
    # Delete image
    if cast.image_filename:
        try:
            filepath = os.path.join(current_app.root_path, 'static', 'uploads', 'casts', cast.image_filename)
            if os.path.exists(filepath):
                os.remove(filepath)
        except:
            pass
    
    db.session.delete(cast)
    db.session.commit()
    
    flash(f'キャスト「{cast_name}」を削除しました。', 'success')
    return redirect(url_for('shop_admin.casts'))


@shop_admin_bp.route('/casts/reorder', methods=['POST'])
@login_required
@owner_required
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
    """Save uploaded cast image and return filename."""
    from ..utils.helpers import validate_image_file
    
    is_valid, error_message = validate_image_file(file)
    if not is_valid:
        return None
    
    # Create unique filename
    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = f"cast_{shop_id}_{uuid.uuid4().hex[:8]}.{ext}"
    
    # Ensure upload directory exists
    upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'casts')
    os.makedirs(upload_dir, exist_ok=True)
    
    # Save file
    filepath = os.path.join(upload_dir, filename)
    file.seek(0)  # Reset file position
    file.save(filepath)
    
    return filename
