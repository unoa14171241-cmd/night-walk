"""
Night-Walk MVP - Admin Routes (運営管理)
"""
import os
import uuid
import secrets
from datetime import datetime, date
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from ..extensions import db
from ..models.shop import Shop, VacancyStatus
from ..models.user import User, ShopMember
from ..models.billing import Subscription
from ..models.audit import AuditLog
from ..models.content import Announcement, Advertisement
from ..models.commission import CommissionRate, Commission, MonthlyBilling, get_default_commission, DEFAULT_COMMISSION_BY_CATEGORY
from ..models.gift import Cast
from ..models.customer import Customer
from ..utils.decorators import admin_required
from ..utils.logger import audit_log

admin_bp = Blueprint('admin', __name__)

# Allowed image extensions
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@admin_bp.route('/')
@admin_required
def dashboard():
    """Admin dashboard."""
    # Get statistics
    total_shops = Shop.query.count()
    active_shops = Shop.query.filter_by(is_active=True).count()
    published_shops = Shop.query.filter_by(is_published=True, is_active=True).count()
    
    # Vacancy status breakdown
    vacancy_stats = db.session.query(
        VacancyStatus.status, db.func.count(VacancyStatus.id)
    ).group_by(VacancyStatus.status).all()
    vacancy_stats = dict(vacancy_stats)
    
    # Recent activity
    recent_logs = AuditLog.query.order_by(
        AuditLog.created_at.desc()
    ).limit(20).all()
    
    # Billing status
    trial_count = Subscription.query.filter_by(status='trial').count()
    active_count = Subscription.query.filter_by(status='active').count()
    past_due_count = Subscription.query.filter_by(status='past_due').count()
    
    return render_template('admin/dashboard.html',
                          total_shops=total_shops,
                          active_shops=active_shops,
                          published_shops=published_shops,
                          vacancy_stats=vacancy_stats,
                          recent_logs=recent_logs,
                          trial_count=trial_count,
                          active_count=active_count,
                          past_due_count=past_due_count)


@admin_bp.route('/shops')
@admin_required
def shops():
    """List all shops."""
    shops = Shop.query.order_by(Shop.created_at.desc()).all()
    return render_template('admin/shops.html', shops=shops)


@admin_bp.route('/shops/new', methods=['GET', 'POST'])
@admin_required
def new_shop():
    """Create new shop."""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        area = request.form.get('area', '')
        category = request.form.get('category', '')
        phone = request.form.get('phone', '').strip()
        
        errors = []
        if not name:
            errors.append('店舗名は必須です。')
        if not category or category not in Shop.CATEGORIES:
            errors.append('カテゴリを選択してください。')
        
        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('admin/shop_form.html', 
                                  shop=None, 
                                  areas=Shop.AREAS,
                                  categories=Shop.CATEGORIES,
                                  category_labels=Shop.CATEGORY_LABELS)
        
        shop = Shop(
            name=name,
            area=area,
            category=category,
            phone=phone,
            address=request.form.get('address', '').strip(),
            business_hours=request.form.get('business_hours', '').strip(),
            price_range=request.form.get('price_range', '').strip(),
            description=request.form.get('description', '').strip(),
        )
        
        db.session.add(shop)
        db.session.flush()  # Get shop.id
        
        # Create vacancy status
        vacancy = VacancyStatus(shop_id=shop.id)
        db.session.add(vacancy)
        
        # Create trial subscription
        subscription = Subscription(shop_id=shop.id, status='trial')
        db.session.add(subscription)
        
        # ============================================
        # 自動でオーナー・スタッフアカウントを作成
        # ============================================
        # パスワード生成（8文字のランダム文字列）
        owner_password = secrets.token_urlsafe(6)
        staff_password = secrets.token_urlsafe(6)
        
        # オーナーアカウント作成
        owner_login_id = f"{name}_owner"
        owner = User(
            email=owner_login_id,
            name=f"【{name}】オーナー",
            role=User.ROLE_OWNER,
        )
        owner.set_password(owner_password)
        db.session.add(owner)
        db.session.flush()
        
        # オーナーを店舗に紐付け
        owner_membership = ShopMember(shop_id=shop.id, user_id=owner.id, role=ShopMember.ROLE_OWNER)
        db.session.add(owner_membership)
        
        # スタッフアカウント作成
        staff_login_id = f"{name}_staff"
        staff = User(
            email=staff_login_id,
            name=f"【{name}】スタッフ",
            role=User.ROLE_STAFF,
        )
        staff.set_password(staff_password)
        db.session.add(staff)
        db.session.flush()
        
        # スタッフを店舗に紐付け
        staff_membership = ShopMember(shop_id=shop.id, user_id=staff.id, role=ShopMember.ROLE_STAFF)
        db.session.add(staff_membership)
        
        db.session.commit()
        
        audit_log(AuditLog.ACTION_SHOP_CREATE, 'shop', shop.id,
                 new_value={'name': name, 'area': area, 'category': category})
        
        # 成功メッセージ（ログイン情報を表示）
        flash(f'店舗「{name}」を作成しました。', 'success')
        flash(f'🔑 オーナー: {owner_login_id} / パスワード: {owner_password}', 'info')
        flash(f'🔑 スタッフ: {staff_login_id} / パスワード: {staff_password}', 'info')
        
        return redirect(url_for('admin.shops'))
    
    return render_template('admin/shop_form.html', 
                          shop=None, 
                          areas=Shop.AREAS,
                          categories=Shop.CATEGORIES,
                          category_labels=Shop.CATEGORY_LABELS)


@admin_bp.route('/shops/<int:shop_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_shop(shop_id):
    """Edit existing shop (admin only)."""
    shop = Shop.query.get_or_404(shop_id)
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        area = request.form.get('area', '')
        category = request.form.get('category', '')
        
        errors = []
        if not name:
            errors.append('店舗名は必須です。')
        if not category or category not in Shop.CATEGORIES:
            errors.append('カテゴリを選択してください。')
        
        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('admin/shop_form.html', 
                                  shop=shop, 
                                  areas=Shop.AREAS,
                                  categories=Shop.CATEGORIES,
                                  category_labels=Shop.CATEGORY_LABELS)
        
        # 変更前の値を記録
        old_values = {
            'name': shop.name,
            'area': shop.area,
            'category': shop.category
        }
        
        # 店舗情報を更新
        shop.name = name
        shop.area = area
        shop.category = category
        shop.phone = request.form.get('phone', '').strip()
        shop.address = request.form.get('address', '').strip()
        shop.business_hours = request.form.get('business_hours', '').strip()
        shop.price_range = request.form.get('price_range', '').strip()
        shop.description = request.form.get('description', '').strip()
        
        db.session.commit()
        
        # 監査ログ
        audit_log(AuditLog.ACTION_SHOP_EDIT, 'shop', shop.id,
                 old_value=old_values,
                 new_value={'name': name, 'area': area, 'category': category})
        
        flash(f'店舗「{name}」を更新しました。', 'success')
        return redirect(url_for('admin.shop_detail', shop_id=shop.id))
    
    return render_template('admin/shop_form.html', 
                          shop=shop, 
                          areas=Shop.AREAS,
                          categories=Shop.CATEGORIES,
                          category_labels=Shop.CATEGORY_LABELS)


@admin_bp.route('/shops/<int:shop_id>')
@admin_required
def shop_detail(shop_id):
    """View shop details."""
    shop = Shop.query.get_or_404(shop_id)
    members = shop.members.all()
    # カスタム手数料設定の有無を確認
    custom_rate = CommissionRate.query.filter_by(shop_id=shop_id, is_active=True).first()
    default_commission = get_default_commission(shop.category) if shop.category else 1000
    return render_template('admin/shop_detail.html', 
                          shop=shop, 
                          members=members,
                          custom_rate=custom_rate,
                          default_commission=default_commission)


@admin_bp.route('/shops/<int:shop_id>/toggle', methods=['POST'])
@admin_required
def toggle_shop(shop_id):
    """Toggle shop active status."""
    shop = Shop.query.get_or_404(shop_id)
    old_status = shop.is_active
    shop.is_active = not shop.is_active
    db.session.commit()
    
    audit_log(AuditLog.ACTION_SHOP_TOGGLE, 'shop', shop.id,
             old_value={'is_active': old_status},
             new_value={'is_active': shop.is_active})
    
    status = '有効' if shop.is_active else '無効'
    flash(f'店舗「{shop.name}」を{status}にしました。', 'success')
    return redirect(url_for('admin.shop_detail', shop_id=shop_id))


@admin_bp.route('/shops/<int:shop_id>/add-member', methods=['POST'])
@admin_required
def add_shop_member(shop_id):
    """Add user to shop."""
    shop = Shop.query.get_or_404(shop_id)
    email = request.form.get('email', '').strip().lower()
    role = request.form.get('role', 'staff')
    
    user = User.query.filter_by(email=email).first()
    if not user:
        flash('指定されたメールアドレスのユーザーが見つかりません。', 'danger')
        return redirect(url_for('admin.shop_detail', shop_id=shop_id))
    
    existing = ShopMember.query.filter_by(shop_id=shop_id, user_id=user.id).first()
    if existing:
        flash('このユーザーは既にこの店舗のメンバーです。', 'warning')
        return redirect(url_for('admin.shop_detail', shop_id=shop_id))
    
    member = ShopMember(shop_id=shop_id, user_id=user.id, role=role)
    db.session.add(member)
    db.session.commit()
    
    flash(f'{user.name}さんを店舗メンバーに追加しました。', 'success')
    return redirect(url_for('admin.shop_detail', shop_id=shop_id))


@admin_bp.route('/users')
@admin_required
def users():
    """List all users."""
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=users)


@admin_bp.route('/users/new', methods=['GET', 'POST'])
@admin_required
def new_user():
    """Create new user."""
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        name = request.form.get('name', '').strip()
        password = request.form.get('password', '')
        role = request.form.get('role', 'staff')
        
        if not email or not name or not password:
            flash('全ての項目を入力してください。', 'danger')
            return render_template('admin/user_form.html', user=None)
        
        if User.query.filter_by(email=email).first():
            flash('このメールアドレスは既に使用されています。', 'danger')
            return render_template('admin/user_form.html', user=None)
        
        user = User(email=email, name=name, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        flash(f'ユーザー「{name}」を作成しました。', 'success')
        return redirect(url_for('admin.users'))
    
    return render_template('admin/user_form.html', user=None)


@admin_bp.route('/billing')
@admin_required
def billing():
    """Billing overview."""
    subscriptions = db.session.query(
        Subscription, Shop
    ).join(Shop).order_by(Subscription.status, Shop.name).all()
    
    return render_template('admin/billing.html', subscriptions=subscriptions)


@admin_bp.route('/audit')
@admin_required
def audit():
    """Audit log viewer."""
    page = request.args.get('page', 1, type=int)
    logs = AuditLog.query.order_by(
        AuditLog.created_at.desc()
    ).paginate(page=page, per_page=50)
    
    return render_template('admin/audit.html', logs=logs)


# ============================================
# Announcements Management
# ============================================

@admin_bp.route('/announcements')
@admin_required
def announcements():
    """List all announcements."""
    items = Announcement.query.order_by(Announcement.priority.desc(), Announcement.created_at.desc()).all()
    return render_template('admin/announcements.html', announcements=items)


@admin_bp.route('/announcements/new', methods=['GET', 'POST'])
@admin_required
def new_announcement():
    """Create new announcement."""
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        link_url = request.form.get('link_url', '').strip()
        link_text = request.form.get('link_text', '').strip()
        priority = int(request.form.get('priority', 0))
        is_active = request.form.get('is_active') == 'on'
        
        starts_at = None
        ends_at = None
        
        starts_at_str = request.form.get('starts_at', '').strip()
        if starts_at_str:
            try:
                starts_at = datetime.strptime(starts_at_str, '%Y-%m-%dT%H:%M')
            except ValueError:
                pass
        
        ends_at_str = request.form.get('ends_at', '').strip()
        if ends_at_str:
            try:
                ends_at = datetime.strptime(ends_at_str, '%Y-%m-%dT%H:%M')
            except ValueError:
                pass
        
        if not title:
            flash('タイトルは必須です。', 'danger')
            return render_template('admin/announcement_form.html', announcement=None)
        
        announcement = Announcement(
            title=title,
            content=content,
            link_url=link_url or None,
            link_text=link_text or None,
            priority=priority,
            is_active=is_active,
            starts_at=starts_at,
            ends_at=ends_at
        )
        db.session.add(announcement)
        db.session.commit()
        
        flash('お知らせを作成しました。', 'success')
        return redirect(url_for('admin.announcements'))
    
    return render_template('admin/announcement_form.html', announcement=None)


@admin_bp.route('/announcements/<int:id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_announcement(id):
    """Edit announcement."""
    announcement = Announcement.query.get_or_404(id)
    
    if request.method == 'POST':
        announcement.title = request.form.get('title', '').strip() or announcement.title
        announcement.content = request.form.get('content', '').strip()
        announcement.link_url = request.form.get('link_url', '').strip() or None
        announcement.link_text = request.form.get('link_text', '').strip() or None
        announcement.priority = int(request.form.get('priority', 0))
        announcement.is_active = request.form.get('is_active') == 'on'
        
        starts_at_str = request.form.get('starts_at', '').strip()
        if starts_at_str:
            try:
                announcement.starts_at = datetime.strptime(starts_at_str, '%Y-%m-%dT%H:%M')
            except ValueError:
                pass
        else:
            announcement.starts_at = None
        
        ends_at_str = request.form.get('ends_at', '').strip()
        if ends_at_str:
            try:
                announcement.ends_at = datetime.strptime(ends_at_str, '%Y-%m-%dT%H:%M')
            except ValueError:
                pass
        else:
            announcement.ends_at = None
        
        db.session.commit()
        
        flash('お知らせを更新しました。', 'success')
        return redirect(url_for('admin.announcements'))
    
    return render_template('admin/announcement_form.html', announcement=announcement)


@admin_bp.route('/announcements/<int:id>/delete', methods=['POST'])
@admin_required
def delete_announcement(id):
    """Delete announcement."""
    announcement = Announcement.query.get_or_404(id)
    db.session.delete(announcement)
    db.session.commit()
    
    flash('お知らせを削除しました。', 'success')
    return redirect(url_for('admin.announcements'))


# ============================================
# Advertisements Management
# ============================================

@admin_bp.route('/advertisements')
@admin_required
def advertisements():
    """List all advertisements."""
    items = Advertisement.query.order_by(Advertisement.position, Advertisement.priority.desc()).all()
    return render_template('admin/advertisements.html', 
                          advertisements=items,
                          position_labels=Advertisement.POSITION_LABELS)


@admin_bp.route('/advertisements/new', methods=['GET', 'POST'])
@admin_required
def new_advertisement():
    """Create new advertisement."""
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        link_url = request.form.get('link_url', '').strip()
        position = request.form.get('position', 'top')
        priority = int(request.form.get('priority', 0))
        is_active = request.form.get('is_active') == 'on'
        
        if not title:
            flash('タイトルは必須です。', 'danger')
            return render_template('admin/advertisement_form.html', 
                                  advertisement=None,
                                  positions=Advertisement.POSITIONS,
                                  position_labels=Advertisement.POSITION_LABELS)
        
        # Handle image upload
        image_filename = None
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename:
                from ..utils.helpers import validate_image_file
                is_valid, error_message = validate_image_file(file)
                
                if is_valid:
                    ext = file.filename.rsplit('.', 1)[1].lower()
                    image_filename = f"ad_{uuid.uuid4().hex[:8]}.{ext}"
                    
                    upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'ads')
                    os.makedirs(upload_dir, exist_ok=True)
                    
                    file.save(os.path.join(upload_dir, image_filename))
                else:
                    flash(error_message, 'danger')
                    return render_template('admin/advertisement_form.html', 
                                          advertisement=None,
                                          positions=Advertisement.POSITIONS,
                                          position_labels=Advertisement.POSITION_LABELS)
        
        # Parse dates
        starts_at = None
        ends_at = None
        
        starts_at_str = request.form.get('starts_at', '').strip()
        if starts_at_str:
            try:
                starts_at = datetime.strptime(starts_at_str, '%Y-%m-%dT%H:%M')
            except ValueError:
                pass
        
        ends_at_str = request.form.get('ends_at', '').strip()
        if ends_at_str:
            try:
                ends_at = datetime.strptime(ends_at_str, '%Y-%m-%dT%H:%M')
            except ValueError:
                pass
        
        advertisement = Advertisement(
            title=title,
            image_filename=image_filename,
            image_url=request.form.get('image_url', '').strip() or None,
            link_url=link_url or None,
            position=position,
            priority=priority,
            is_active=is_active,
            starts_at=starts_at,
            ends_at=ends_at
        )
        db.session.add(advertisement)
        db.session.commit()
        
        flash('広告を作成しました。', 'success')
        return redirect(url_for('admin.advertisements'))
    
    return render_template('admin/advertisement_form.html', 
                          advertisement=None,
                          positions=Advertisement.POSITIONS,
                          position_labels=Advertisement.POSITION_LABELS)


@admin_bp.route('/advertisements/<int:id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_advertisement(id):
    """Edit advertisement."""
    advertisement = Advertisement.query.get_or_404(id)
    
    if request.method == 'POST':
        advertisement.title = request.form.get('title', '').strip() or advertisement.title
        advertisement.link_url = request.form.get('link_url', '').strip() or None
        advertisement.position = request.form.get('position', 'top')
        advertisement.priority = int(request.form.get('priority', 0))
        advertisement.is_active = request.form.get('is_active') == 'on'
        
        # Handle image upload
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename and allowed_file(file.filename):
                # Delete old image
                if advertisement.image_filename:
                    old_path = os.path.join(current_app.root_path, 'static', 'uploads', 'ads', advertisement.image_filename)
                    if os.path.exists(old_path):
                        try:
                            os.remove(old_path)
                        except:
                            pass
                
                ext = file.filename.rsplit('.', 1)[1].lower()
                image_filename = f"ad_{uuid.uuid4().hex[:8]}.{ext}"
                
                upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'ads')
                os.makedirs(upload_dir, exist_ok=True)
                
                file.save(os.path.join(upload_dir, image_filename))
                advertisement.image_filename = image_filename
        
        # Update image URL if provided
        image_url = request.form.get('image_url', '').strip()
        if image_url:
            advertisement.image_url = image_url
        
        # Parse dates
        starts_at_str = request.form.get('starts_at', '').strip()
        if starts_at_str:
            try:
                advertisement.starts_at = datetime.strptime(starts_at_str, '%Y-%m-%dT%H:%M')
            except ValueError:
                pass
        else:
            advertisement.starts_at = None
        
        ends_at_str = request.form.get('ends_at', '').strip()
        if ends_at_str:
            try:
                advertisement.ends_at = datetime.strptime(ends_at_str, '%Y-%m-%dT%H:%M')
            except ValueError:
                pass
        else:
            advertisement.ends_at = None
        
        db.session.commit()
        
        flash('広告を更新しました。', 'success')
        return redirect(url_for('admin.advertisements'))
    
    return render_template('admin/advertisement_form.html', 
                          advertisement=advertisement,
                          positions=Advertisement.POSITIONS,
                          position_labels=Advertisement.POSITION_LABELS)


@admin_bp.route('/advertisements/<int:id>/delete', methods=['POST'])
@admin_required
def delete_advertisement(id):
    """Delete advertisement."""
    advertisement = Advertisement.query.get_or_404(id)
    
    # Delete image file
    if advertisement.image_filename:
        filepath = os.path.join(current_app.root_path, 'static', 'uploads', 'ads', advertisement.image_filename)
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except:
                pass
    
    db.session.delete(advertisement)
    db.session.commit()
    
    flash('広告を削除しました。', 'success')
    return redirect(url_for('admin.advertisements'))


# ============================================
# Commission Management (送客手数料)
# ============================================

@admin_bp.route('/commissions')
@admin_required
def commissions():
    """Commission list and management."""
    # Filter parameters
    shop_id = request.args.get('shop_id', type=int)
    year = request.args.get('year', date.today().year, type=int)
    month = request.args.get('month', type=int)
    status = request.args.get('status', '')
    
    query = Commission.query
    
    if shop_id:
        query = query.filter_by(shop_id=shop_id)
    if month:
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1)
        else:
            end_date = date(year, month + 1, 1)
        query = query.filter(Commission.visit_date >= start_date, Commission.visit_date < end_date)
    if status:
        query = query.filter_by(status=status)
    
    commissions_list = query.order_by(Commission.visit_date.desc(), Commission.id.desc()).limit(200).all()
    shops = Shop.query.filter_by(is_active=True).order_by(Shop.name).all()
    
    # Summary
    total_amount = sum(c.commission_amount for c in commissions_list if c.status != Commission.STATUS_CANCELLED)
    total_count = len([c for c in commissions_list if c.status != Commission.STATUS_CANCELLED])
    
    return render_template('admin/commissions.html',
                          commissions=commissions_list,
                          shops=shops,
                          total_amount=total_amount,
                          total_count=total_count,
                          selected_shop=shop_id,
                          selected_year=year,
                          selected_month=month,
                          selected_status=status,
                          statuses=Commission.STATUS_LABELS,
                          sources=Commission.SOURCE_LABELS)


@admin_bp.route('/commissions/new', methods=['GET', 'POST'])
@admin_required
def new_commission():
    """Create new commission (manual entry)."""
    if request.method == 'POST':
        shop_id = request.form.get('shop_id', type=int)
        visit_date_str = request.form.get('visit_date', '')
        guest_count = request.form.get('guest_count', 1, type=int)
        sales_amount = request.form.get('sales_amount', type=int)
        source = request.form.get('source', Commission.SOURCE_WALK_IN)
        notes = request.form.get('notes', '').strip()
        
        if not shop_id or not visit_date_str:
            flash('店舗と来店日は必須です。', 'danger')
            shops = Shop.query.filter_by(is_active=True).order_by(Shop.name).all()
            return render_template('admin/commission_form.html', shops=shops, commission=None)
        
        try:
            visit_date = datetime.strptime(visit_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('来店日の形式が不正です。', 'danger')
            shops = Shop.query.filter_by(is_active=True).order_by(Shop.name).all()
            return render_template('admin/commission_form.html', shops=shops, commission=None)
        
        # Get commission rate
        rate = CommissionRate.query.filter_by(shop_id=shop_id, is_active=True).first()
        shop = Shop.query.get(shop_id)
        
        if rate:
            commission_amount = rate.calculate(sales_amount, guest_count)
        else:
            # Manual input or category default
            commission_amount = request.form.get('commission_amount', type=int)
            if not commission_amount:
                # カテゴリ別デフォルト手数料を使用
                default_rate = get_default_commission(shop.category) if shop else 1000
                commission_amount = default_rate * guest_count
        
        commission = Commission(
            shop_id=shop_id,
            source=source,
            visit_date=visit_date,
            guest_count=guest_count,
            sales_amount=sales_amount,
            commission_amount=commission_amount,
            status=Commission.STATUS_CONFIRMED,
            confirmed_at=datetime.utcnow(),
            notes=notes
        )
        
        # Link to monthly billing
        billing = MonthlyBilling.get_or_create(shop_id, visit_date.year, visit_date.month)
        commission.monthly_billing = billing
        
        db.session.add(commission)
        db.session.commit()
        
        flash(f'送客手数料を登録しました（¥{commission_amount:,}）', 'success')
        return redirect(url_for('admin.commissions'))
    
    shops = Shop.query.filter_by(is_active=True).order_by(Shop.name).all()
    return render_template('admin/commission_form.html', 
                          shops=shops, 
                          commission=None,
                          sources=Commission.SOURCE_LABELS)


@admin_bp.route('/commissions/<int:id>/confirm', methods=['POST'])
@admin_required
def confirm_commission(id):
    """Confirm a pending commission."""
    commission = Commission.query.get_or_404(id)
    commission.confirm()
    db.session.commit()
    
    flash('手数料を確定しました。', 'success')
    return redirect(url_for('admin.commissions'))


@admin_bp.route('/commissions/<int:id>/cancel', methods=['POST'])
@admin_required
def cancel_commission(id):
    """Cancel a commission."""
    commission = Commission.query.get_or_404(id)
    commission.cancel()
    db.session.commit()
    
    flash('手数料をキャンセルしました。', 'success')
    return redirect(url_for('admin.commissions'))


@admin_bp.route('/commissions/<int:id>/delete', methods=['POST'])
@admin_required
def delete_commission(id):
    """Delete a commission."""
    commission = Commission.query.get_or_404(id)
    db.session.delete(commission)
    db.session.commit()
    
    flash('手数料を削除しました。', 'success')
    return redirect(url_for('admin.commissions'))


# ============================================
# Commission Rate Settings
# ============================================

@admin_bp.route('/commission-rates')
@admin_required
def commission_rates():
    """Commission rate settings."""
    rates = db.session.query(CommissionRate, Shop).join(Shop).order_by(Shop.name).all()
    shops_without_rate = Shop.query.filter(
        ~Shop.id.in_(db.session.query(CommissionRate.shop_id)),
        Shop.is_active == True
    ).order_by(Shop.name).all()
    
    return render_template('admin/commission_rates.html',
                          rates=rates,
                          shops_without_rate=shops_without_rate,
                          get_default_commission=get_default_commission,
                          default_commissions=DEFAULT_COMMISSION_BY_CATEGORY)


@admin_bp.route('/commission-rates/new', methods=['GET', 'POST'])
@admin_required
def new_commission_rate():
    """Create new commission rate."""
    if request.method == 'POST':
        shop_id = request.form.get('shop_id', type=int)
        
        # Check if rate already exists
        existing = CommissionRate.query.filter_by(shop_id=shop_id).first()
        if existing:
            flash('この店舗には既に手数料設定があります。', 'warning')
            return redirect(url_for('admin.edit_commission_rate', shop_id=shop_id))
        
        rate = CommissionRate(shop_id=shop_id)
        rate.commission_type = request.form.get('commission_type', 'fixed')
        rate.fixed_amount = request.form.get('fixed_amount', 1000, type=int)
        rate.percentage_rate = request.form.get('percentage_rate', 10.0, type=float)
        rate.min_amount = request.form.get('min_amount', 0, type=int)
        rate.is_active = request.form.get('is_active') == 'on'
        
        db.session.add(rate)
        db.session.commit()
        
        flash('手数料設定を作成しました。', 'success')
        return redirect(url_for('admin.commission_rates'))
    
    shops = Shop.query.filter(
        ~Shop.id.in_(db.session.query(CommissionRate.shop_id)),
        Shop.is_active == True
    ).order_by(Shop.name).all()
    
    return render_template('admin/commission_rate_form.html', 
                          shop=None, 
                          shops=shops,
                          rate=None,
                          types=CommissionRate.TYPE_LABELS)


@admin_bp.route('/commission-rates/<int:shop_id>', methods=['GET', 'POST'])
@admin_required
def edit_commission_rate(shop_id):
    """Edit commission rate for shop."""
    shop = Shop.query.get_or_404(shop_id)
    rate = CommissionRate.query.filter_by(shop_id=shop_id).first()
    
    if request.method == 'POST':
        if not rate:
            rate = CommissionRate(shop_id=shop_id)
            db.session.add(rate)
        
        rate.commission_type = request.form.get('commission_type', 'fixed')
        rate.fixed_amount = request.form.get('fixed_amount', 1000, type=int)
        rate.percentage_rate = request.form.get('percentage_rate', 10.0, type=float)
        rate.min_amount = request.form.get('min_amount', 0, type=int)
        rate.is_active = request.form.get('is_active') == 'on'
        
        db.session.commit()
        
        flash(f'{shop.name}の手数料設定を保存しました', 'success')
        return redirect(url_for('admin.commission_rates'))
    
    return render_template('admin/commission_rate_form.html', 
                          shop=shop, 
                          shops=None,
                          rate=rate,
                          types=CommissionRate.TYPE_LABELS)


# ============================================
# Monthly Billing
# ============================================

@admin_bp.route('/monthly-billings')
@admin_required
def monthly_billings():
    """Monthly billing list."""
    year = request.args.get('year', date.today().year, type=int)
    shop_id = request.args.get('shop_id', type=int)
    
    query = db.session.query(MonthlyBilling, Shop).join(Shop).filter(
        MonthlyBilling.year == year
    )
    
    if shop_id:
        query = query.filter(MonthlyBilling.shop_id == shop_id)
    
    billings = query.order_by(MonthlyBilling.month.desc(), Shop.name).all()
    
    # Summary by month
    monthly_totals = {}
    for billing, shop in billings:
        if billing.month not in monthly_totals:
            monthly_totals[billing.month] = {'count': 0, 'amount': 0}
        monthly_totals[billing.month]['count'] += billing.total_commissions
        monthly_totals[billing.month]['amount'] += billing.total_amount
    
    shops = Shop.query.filter_by(is_active=True).order_by(Shop.name).all()
    
    return render_template('admin/monthly_billings.html',
                          billings=billings,
                          year=year,
                          selected_shop=shop_id,
                          shops=shops,
                          monthly_totals=monthly_totals,
                          statuses=MonthlyBilling.STATUS_LABELS)


@admin_bp.route('/monthly-billings/<int:id>')
@admin_required
def monthly_billing_detail(id):
    """Monthly billing detail."""
    billing = MonthlyBilling.query.get_or_404(id)
    commissions_list = billing.commissions.order_by(Commission.visit_date.desc()).all()
    
    return render_template('admin/monthly_billing_detail.html',
                          billing=billing,
                          commissions=commissions_list,
                          statuses=Commission.STATUS_LABELS)


@admin_bp.route('/monthly-billings/<int:id>/recalculate', methods=['POST'])
@admin_required
def recalculate_monthly_billing(id):
    """Recalculate monthly billing totals."""
    billing = MonthlyBilling.query.get_or_404(id)
    billing.recalculate()
    db.session.commit()
    
    flash(f'請求金額を再計算しました（合計: ¥{billing.total_amount:,}）', 'success')
    return redirect(url_for('admin.monthly_billing_detail', id=id))


@admin_bp.route('/monthly-billings/<int:id>/close', methods=['POST'])
@admin_required
def close_monthly_billing(id):
    """Close monthly billing."""
    billing = MonthlyBilling.query.get_or_404(id)
    
    if billing.status != MonthlyBilling.STATUS_OPEN:
        flash('この請求は既に締め済みです。', 'warning')
        return redirect(url_for('admin.monthly_billing_detail', id=id))
    
    billing.close()
    db.session.commit()
    
    flash(f'{billing.period_display}の請求を締めました（合計: ¥{billing.total_amount:,}）', 'success')
    return redirect(url_for('admin.monthly_billing_detail', id=id))


@admin_bp.route('/monthly-billings/<int:id>/invoice', methods=['POST'])
@admin_required
def invoice_monthly_billing(id):
    """Mark as invoiced."""
    billing = MonthlyBilling.query.get_or_404(id)
    
    if billing.status not in [MonthlyBilling.STATUS_CLOSED, MonthlyBilling.STATUS_OPEN]:
        flash('この請求は請求済みです。', 'warning')
        return redirect(url_for('admin.monthly_billing_detail', id=id))
    
    if billing.status == MonthlyBilling.STATUS_OPEN:
        billing.close()
    
    billing.invoice()
    db.session.commit()
    
    flash(f'{billing.period_display}を請求済みにしました（支払期限: {billing.due_date}）', 'success')
    return redirect(url_for('admin.monthly_billing_detail', id=id))


@admin_bp.route('/monthly-billings/<int:id>/mark-paid', methods=['POST'])
@admin_required
def mark_paid_monthly_billing(id):
    """Mark as paid."""
    billing = MonthlyBilling.query.get_or_404(id)
    billing.mark_paid()
    db.session.commit()
    
    flash(f'{billing.period_display}を支払済みにしました', 'success')
    return redirect(url_for('admin.monthly_billing_detail', id=id))


# ============================================
# Invoice Generation & Sending
# ============================================

@admin_bp.route('/monthly-billings/<int:id>/preview-invoice')
@admin_required
def preview_invoice(id):
    """Preview invoice PDF in browser."""
    from flask import Response
    from ..services.invoice_service import InvoiceService
    
    billing = MonthlyBilling.query.get_or_404(id)
    
    try:
        pdf_content = InvoiceService.preview_pdf(billing)
        db.session.commit()  # Save invoice_number if generated
        
        return Response(
            pdf_content,
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'inline; filename=invoice_{billing.invoice_number}.pdf'
            }
        )
    except Exception as e:
        current_app.logger.error(f"Invoice preview failed: {e}")
        flash(f'請求書の生成に失敗しました: {e}', 'danger')
        return redirect(url_for('admin.monthly_billing_detail', id=id))


@admin_bp.route('/monthly-billings/<int:id>/download-invoice')
@admin_required
def download_invoice(id):
    """Download invoice PDF."""
    from flask import Response
    from ..services.invoice_service import InvoiceService
    
    billing = MonthlyBilling.query.get_or_404(id)
    
    try:
        pdf_content = InvoiceService.preview_pdf(billing)
        db.session.commit()
        
        # URL encode the filename for Japanese characters
        filename = f'invoice_{billing.invoice_number}.pdf'
        
        return Response(
            pdf_content,
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"'
            }
        )
    except Exception as e:
        current_app.logger.error(f"Invoice download failed: {e}")
        flash(f'請求書の生成に失敗しました: {e}', 'danger')
        return redirect(url_for('admin.monthly_billing_detail', id=id))


@admin_bp.route('/monthly-billings/<int:id>/send-invoice', methods=['GET', 'POST'])
@admin_required
def send_invoice(id):
    """Send invoice via email."""
    from ..services.invoice_service import InvoiceService
    
    billing = MonthlyBilling.query.get_or_404(id)
    
    if request.method == 'POST':
        recipient_email = request.form.get('email', '').strip()
        
        if not recipient_email:
            flash('送付先メールアドレスを入力してください', 'danger')
            return redirect(url_for('admin.send_invoice', id=id))
        
        try:
            success = InvoiceService.send_invoice(billing, recipient_email)
            
            if success:
                db.session.commit()
                flash(f'請求書を {recipient_email} に送付しました', 'success')
                return redirect(url_for('admin.monthly_billing_detail', id=id))
            else:
                flash('請求書の送付に失敗しました', 'danger')
        except Exception as e:
            flash(f'エラー: {e}', 'danger')
        
        return redirect(url_for('admin.send_invoice', id=id))
    
    # GET: Show send form
    # Default email from shop owner
    default_email = ''
    if billing.shop.members:
        owner = billing.shop.members.filter_by(role='owner').first()
        if owner and owner.user:
            default_email = owner.user.email
    
    return render_template('admin/send_invoice.html',
                          billing=billing,
                          default_email=default_email)


# ============================================
# Ranking Management (キャストランキング)
# ============================================

@admin_bp.route('/rankings')
@admin_required
def rankings():
    """ランキング管理トップ"""
    from ..models.ranking import CastMonthlyRanking, RankingConfig, AREA_DEFINITIONS
    from ..services.ranking_service import RankingService
    
    # パラメータ
    year = request.args.get('year', date.today().year, type=int)
    month = request.args.get('month', type=int)
    area = request.args.get('area', 'okayama')
    
    # 前月をデフォルトにする（当月はまだ集計中の可能性）
    if not month:
        if date.today().month == 1:
            month = 12
            year = year - 1
        else:
            month = date.today().month - 1
    
    # ランキング取得
    rankings_list = CastMonthlyRanking.get_ranking(area, year, month, limit=100, finalized_only=False)
    
    # 統計
    finalized_count = sum(1 for r in rankings_list if r.is_finalized)
    total_pv = sum(r.pv_count for r in rankings_list)
    total_gifts = sum(r.gift_points for r in rankings_list)
    
    # エリア一覧
    active_areas = RankingService.get_active_areas()
    
    return render_template('admin/rankings.html',
                          rankings=rankings_list,
                          year=year,
                          month=month,
                          area=area,
                          areas=active_areas,
                          area_definitions=AREA_DEFINITIONS,
                          finalized_count=finalized_count,
                          total_pv=total_pv,
                          total_gifts=total_gifts)


@admin_bp.route('/rankings/calculate', methods=['POST'])
@admin_required
def calculate_rankings():
    """ランキング計算（手動実行）"""
    from ..services.ranking_service import RankingService
    
    year = request.form.get('year', date.today().year, type=int)
    month = request.form.get('month', date.today().month, type=int)
    area = request.form.get('area', 'okayama')
    finalize = request.form.get('finalize') == 'on'
    
    try:
        if area == 'all':
            # 全エリア計算
            for area_key in RankingService.get_active_areas():
                RankingService.calculate_area_ranking(area_key, year, month, finalize=finalize)
            flash(f'{year}年{month}月の全エリアランキングを{"確定" if finalize else "計算"}しました', 'success')
        else:
            RankingService.calculate_area_ranking(area, year, month, finalize=finalize)
            flash(f'{year}年{month}月のランキングを{"確定" if finalize else "計算"}しました', 'success')
    except Exception as e:
        flash(f'ランキング計算エラー: {e}', 'danger')
    
    return redirect(url_for('admin.rankings', year=year, month=month, area=area))


@admin_bp.route('/rankings/finalize-month', methods=['POST'])
@admin_required
def finalize_month_rankings():
    """月次ランキング確定（全エリア・バッジ付与）"""
    from ..services.ranking_service import RankingService
    
    year = request.form.get('year', type=int)
    month = request.form.get('month', type=int)
    
    if not year or not month:
        flash('年月を指定してください', 'danger')
        return redirect(url_for('admin.rankings'))
    
    try:
        results = RankingService.finalize_month(year, month)
        total = sum(len(r) for r in results.values())
        flash(f'{year}年{month}月のランキングを確定しました（{total}件、TOP10にバッジ付与）', 'success')
    except Exception as e:
        flash(f'ランキング確定エラー: {e}', 'danger')
    
    return redirect(url_for('admin.rankings', year=year, month=month))


@admin_bp.route('/rankings/<int:id>/override', methods=['POST'])
@admin_required
def override_ranking(id):
    """ランキング強制変更"""
    from ..services.ranking_service import RankingService
    from ..models.ranking import CastMonthlyRanking
    
    ranking = CastMonthlyRanking.query.get_or_404(id)
    new_rank = request.form.get('new_rank', type=int)
    reason = request.form.get('reason', '').strip()
    
    if not new_rank or not reason:
        flash('新しい順位と理由を入力してください', 'danger')
        return redirect(url_for('admin.rankings', 
                                year=ranking.year, month=ranking.month, area=ranking.area))
    
    success = RankingService.override_ranking(id, new_rank, reason, current_user.id)
    
    if success:
        flash(f'{ranking.cast.name_display}の順位を{new_rank}位に変更しました', 'success')
    else:
        flash('順位変更に失敗しました', 'danger')
    
    return redirect(url_for('admin.rankings', 
                            year=ranking.year, month=ranking.month, area=ranking.area))


@admin_bp.route('/rankings/<int:id>/disqualify', methods=['POST'])
@admin_required
def disqualify_ranking(id):
    """キャスト失格（ランキング除外）"""
    from ..services.ranking_service import RankingService
    from ..models.ranking import CastMonthlyRanking
    
    ranking = CastMonthlyRanking.query.get_or_404(id)
    reason = request.form.get('reason', '').strip()
    
    if not reason:
        flash('失格理由を入力してください', 'danger')
        return redirect(url_for('admin.rankings', 
                                year=ranking.year, month=ranking.month, area=ranking.area))
    
    success = RankingService.disqualify_cast(id, reason, current_user.id)
    
    if success:
        flash(f'{ranking.cast.name_display}を失格にしました', 'success')
    else:
        flash('失格処理に失敗しました', 'danger')
    
    return redirect(url_for('admin.rankings', 
                            year=ranking.year, month=ranking.month, area=ranking.area))


@admin_bp.route('/rankings/config', methods=['GET', 'POST'])
@admin_required
def ranking_config():
    """ランキング係数設定"""
    from ..models.ranking import RankingConfig
    
    if request.method == 'POST':
        pv_weight = request.form.get('pv_weight', '1.0')
        gift_weight = request.form.get('gift_weight', '1.0')
        ranking_top_count = request.form.get('ranking_top_count', '100')
        pv_unique_hours = request.form.get('pv_unique_hours', '24')
        
        try:
            # バリデーション
            float(pv_weight)
            float(gift_weight)
            int(ranking_top_count)
            int(pv_unique_hours)
            
            # 保存
            RankingConfig.set('pv_weight', pv_weight, current_user.id)
            RankingConfig.set('gift_weight', gift_weight, current_user.id)
            RankingConfig.set('ranking_top_count', ranking_top_count, current_user.id)
            RankingConfig.set('pv_unique_hours', pv_unique_hours, current_user.id)
            db.session.commit()
            
            flash('ランキング設定を保存しました', 'success')
        except ValueError:
            flash('入力値が不正です', 'danger')
        
        return redirect(url_for('admin.ranking_config'))
    
    # 現在の設定を取得
    configs = RankingConfig.get_all()
    
    return render_template('admin/ranking_config.html', configs=configs)


@admin_bp.route('/rankings/badges')
@admin_required
def ranking_badges():
    """バッジ管理"""
    from ..models.ranking import CastBadgeHistory
    
    # パラメータ
    year = request.args.get('year', date.today().year, type=int)
    status = request.args.get('status', '')  # pending_ship, shipped, all
    
    query = CastBadgeHistory.query.filter(CastBadgeHistory.year == year)
    
    if status == 'pending_ship':
        query = query.filter(
            CastBadgeHistory.badge_type == 'area_top1',
            CastBadgeHistory.prize_shipped == False
        )
    elif status == 'shipped':
        query = query.filter(CastBadgeHistory.prize_shipped == True)
    
    badges = query.order_by(
        CastBadgeHistory.year.desc(),
        CastBadgeHistory.month.desc(),
        CastBadgeHistory.badge_type
    ).all()
    
    return render_template('admin/ranking_badges.html',
                          badges=badges,
                          year=year,
                          status=status)


@admin_bp.route('/rankings/badges/<int:id>/ship', methods=['POST'])
@admin_required
def ship_badge_prize(id):
    """特典発送完了"""
    from ..models.ranking import CastBadgeHistory
    
    badge = CastBadgeHistory.query.get_or_404(id)
    tracking_number = request.form.get('tracking_number', '').strip()
    
    badge.prize_shipped = True
    badge.shipped_at = datetime.utcnow()
    badge.tracking_number = tracking_number
    db.session.commit()
    
    flash(f'{badge.cast.name_display}への特典発送を完了しました', 'success')
    return redirect(url_for('admin.ranking_badges'))


# ============================================
# Ad Entitlement Management (広告権利管理)
# ============================================

@admin_bp.route('/entitlements')
@admin_required
def entitlements():
    """広告権利一覧"""
    from ..models.ad_entitlement import AdEntitlement, AdPlacement
    
    # フィルタパラメータ
    target_type = request.args.get('target_type', '')
    placement_type = request.args.get('placement_type', '')
    status = request.args.get('status', 'active')  # active, expired, all
    
    query = AdEntitlement.query
    
    if target_type:
        query = query.filter(AdEntitlement.target_type == target_type)
    
    if placement_type:
        query = query.filter(AdEntitlement.placement_type == placement_type)
    
    now = datetime.utcnow()
    if status == 'active':
        query = query.filter(
            AdEntitlement.is_active == True,
            AdEntitlement.starts_at <= now,
            AdEntitlement.ends_at >= now
        )
    elif status == 'expired':
        query = query.filter(AdEntitlement.ends_at < now)
    
    entitlements_list = query.order_by(
        AdEntitlement.ends_at.desc(),
        AdEntitlement.created_at.desc()
    ).limit(200).all()
    
    # 統計
    active_count = AdEntitlement.query.filter(
        AdEntitlement.is_active == True,
        AdEntitlement.starts_at <= now,
        AdEntitlement.ends_at >= now
    ).count()
    
    return render_template('admin/entitlements.html',
                          entitlements=entitlements_list,
                          active_count=active_count,
                          selected_target_type=target_type,
                          selected_placement_type=placement_type,
                          selected_status=status,
                          placement_types=AdPlacement.PLACEMENT_TYPES,
                          placement_labels=AdPlacement.PLACEMENT_LABELS,
                          source_labels=AdEntitlement.SOURCE_LABELS)


@admin_bp.route('/entitlements/new', methods=['GET', 'POST'])
@admin_required
def new_entitlement():
    """広告権利を手動付与"""
    from ..models.ad_entitlement import AdEntitlement, AdPlacement
    from ..models.gift import Cast
    
    if request.method == 'POST':
        target_type = request.form.get('target_type')
        target_id = request.form.get('target_id', type=int)
        placement_type = request.form.get('placement_type')
        area = request.form.get('area', '').strip() or None
        priority = request.form.get('priority', 0, type=int)
        starts_at_str = request.form.get('starts_at', '')
        ends_at_str = request.form.get('ends_at', '')
        
        errors = []
        if not target_type or target_type not in ['shop', 'cast']:
            errors.append('対象タイプを選択してください')
        if not target_id:
            errors.append('対象IDを入力してください')
        if not placement_type:
            errors.append('広告枠を選択してください')
        if not starts_at_str or not ends_at_str:
            errors.append('期間を設定してください')
        
        if errors:
            for e in errors:
                flash(e, 'danger')
            shops = Shop.query.filter_by(is_active=True).order_by(Shop.name).all()
            casts = Cast.query.filter_by(is_active=True).order_by(Cast.name).all()
            return render_template('admin/entitlement_form.html',
                                  entitlement=None,
                                  shops=shops,
                                  casts=casts,
                                  placement_types=AdPlacement.PLACEMENT_TYPES,
                                  placement_labels=AdPlacement.PLACEMENT_LABELS,
                                  areas=Shop.AREAS)
        
        try:
            starts_at = datetime.strptime(starts_at_str, '%Y-%m-%dT%H:%M')
            ends_at = datetime.strptime(ends_at_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            flash('日時の形式が不正です', 'danger')
            return redirect(url_for('admin.new_entitlement'))
        
        entitlement = AdEntitlement(
            target_type=target_type,
            target_id=target_id,
            placement_type=placement_type,
            area=area,
            priority=priority,
            starts_at=starts_at,
            ends_at=ends_at,
            source_type=AdEntitlement.SOURCE_MANUAL,
            is_active=True,
            created_by=current_user.id
        )
        db.session.add(entitlement)
        db.session.commit()
        
        # 監査ログ
        audit_log('entitlement.create', 'entitlement', entitlement.id,
                 new_value={'target': f'{target_type}:{target_id}', 'placement': placement_type})
        
        flash('広告権利を付与しました', 'success')
        return redirect(url_for('admin.entitlements'))
    
    shops = Shop.query.filter_by(is_active=True).order_by(Shop.name).all()
    casts = Cast.query.filter_by(is_active=True).order_by(Cast.name).all()
    
    return render_template('admin/entitlement_form.html',
                          entitlement=None,
                          shops=shops,
                          casts=casts,
                          placement_types=AdPlacement.PLACEMENT_TYPES,
                          placement_labels=AdPlacement.PLACEMENT_LABELS,
                          areas=Shop.AREAS)


@admin_bp.route('/entitlements/<int:id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_entitlement(id):
    """広告権利を編集"""
    from ..models.ad_entitlement import AdEntitlement, AdPlacement
    from ..models.gift import Cast
    
    entitlement = AdEntitlement.query.get_or_404(id)
    
    if request.method == 'POST':
        area = request.form.get('area', '').strip() or None
        priority = request.form.get('priority', 0, type=int)
        starts_at_str = request.form.get('starts_at', '')
        ends_at_str = request.form.get('ends_at', '')
        is_active = request.form.get('is_active') == 'on'
        
        try:
            starts_at = datetime.strptime(starts_at_str, '%Y-%m-%dT%H:%M')
            ends_at = datetime.strptime(ends_at_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            flash('日時の形式が不正です', 'danger')
            return redirect(url_for('admin.edit_entitlement', id=id))
        
        old_values = {
            'priority': entitlement.priority,
            'is_active': entitlement.is_active,
        }
        
        entitlement.area = area
        entitlement.priority = priority
        entitlement.starts_at = starts_at
        entitlement.ends_at = ends_at
        entitlement.is_active = is_active
        entitlement.updated_by = current_user.id
        
        db.session.commit()
        
        # 監査ログ
        audit_log('entitlement.edit', 'entitlement', entitlement.id,
                 old_value=old_values,
                 new_value={'priority': priority, 'is_active': is_active})
        
        flash('広告権利を更新しました', 'success')
        return redirect(url_for('admin.entitlements'))
    
    shops = Shop.query.filter_by(is_active=True).order_by(Shop.name).all()
    casts = Cast.query.filter_by(is_active=True).order_by(Cast.name).all()
    
    return render_template('admin/entitlement_form.html',
                          entitlement=entitlement,
                          shops=shops,
                          casts=casts,
                          placement_types=AdPlacement.PLACEMENT_TYPES,
                          placement_labels=AdPlacement.PLACEMENT_LABELS,
                          areas=Shop.AREAS)


@admin_bp.route('/entitlements/<int:id>/deactivate', methods=['POST'])
@admin_required
def deactivate_entitlement(id):
    """広告権利を無効化"""
    from ..models.ad_entitlement import AdEntitlement
    
    entitlement = AdEntitlement.query.get_or_404(id)
    reason = request.form.get('reason', '').strip()
    
    entitlement.deactivate(current_user.id, reason)
    db.session.commit()
    
    # 監査ログ
    audit_log('entitlement.deactivate', 'entitlement', entitlement.id,
             new_value={'reason': reason})
    
    flash('広告権利を無効化しました', 'success')
    return redirect(url_for('admin.entitlements'))


# ============================================
# Store Plan Management (店舗プラン管理)
# ============================================

@admin_bp.route('/store-plans')
@admin_required
def store_plans():
    """店舗プラン一覧"""
    from ..models.store_plan import StorePlan
    
    plan_type = request.args.get('plan_type', '')
    status = request.args.get('status', '')
    
    query = StorePlan.query.join(Shop)
    
    if plan_type:
        query = query.filter(StorePlan.plan_type == plan_type)
    
    if status:
        query = query.filter(StorePlan.status == status)
    
    plans = query.order_by(Shop.name).all()
    
    # 統計
    stats = {
        'total': StorePlan.query.count(),
        'premium': StorePlan.query.filter_by(plan_type=StorePlan.PLAN_PREMIUM, status=StorePlan.STATUS_ACTIVE).count(),
        'standard': StorePlan.query.filter_by(plan_type=StorePlan.PLAN_STANDARD, status=StorePlan.STATUS_ACTIVE).count(),
        'free': StorePlan.query.filter_by(plan_type=StorePlan.PLAN_FREE).count(),
    }
    
    return render_template('admin/store_plans.html',
                          plans=plans,
                          stats=stats,
                          selected_plan_type=plan_type,
                          selected_status=status,
                          plan_types=StorePlan.PLAN_TYPES,
                          plan_labels=StorePlan.PLAN_LABELS)


@admin_bp.route('/store-plans/<int:shop_id>/upgrade', methods=['POST'])
@admin_required
def upgrade_store_plan(shop_id):
    """店舗プランをアップグレード"""
    from ..models.store_plan import StorePlan, StorePlanHistory
    
    new_plan_type = request.form.get('plan_type')
    
    if new_plan_type not in StorePlan.PLAN_TYPES:
        flash('無効なプランタイプです', 'danger')
        return redirect(url_for('admin.store_plans'))
    
    plan = StorePlan.query.filter_by(shop_id=shop_id).first()
    if not plan:
        plan = StorePlan.get_or_create_free(shop_id)
    
    old_plan_type = plan.plan_type
    plan.upgrade(new_plan_type, current_user.id)
    plan.sync_entitlements(current_user.id)
    
    # 履歴記録
    StorePlanHistory.log(
        shop_id=shop_id,
        action='upgraded',
        plan_id=plan.id,
        from_plan=old_plan_type,
        to_plan=new_plan_type,
        user_id=current_user.id
    )
    
    db.session.commit()
    
    flash(f'プランを{StorePlan.PLAN_LABELS[new_plan_type]}に変更しました', 'success')
    return redirect(url_for('admin.store_plans'))


# ============================================
# Customer Management (一般ユーザ管理)
# ============================================

@admin_bp.route('/customers')
@admin_required
def customers():
    """一般ユーザ一覧"""
    # フィルタパラメータ
    status = request.args.get('status', '')  # active, inactive, all
    search = request.args.get('search', '').strip()
    
    query = Customer.query
    
    if status == 'active':
        query = query.filter(Customer.is_active == True)
    elif status == 'inactive':
        query = query.filter(Customer.is_active == False)
    
    if search:
        search_filter = f'%{search}%'
        query = query.filter(
            db.or_(
                Customer.email.ilike(search_filter),
                Customer.nickname.ilike(search_filter),
                Customer.phone.ilike(search_filter)
            )
        )
    
    customers_list = query.order_by(Customer.created_at.desc()).limit(200).all()
    
    # 統計
    total_count = Customer.query.count()
    active_count = Customer.query.filter_by(is_active=True).count()
    verified_count = Customer.query.filter_by(is_verified=True).count()
    
    return render_template('admin/customers.html',
                          customers=customers_list,
                          total_count=total_count,
                          active_count=active_count,
                          verified_count=verified_count,
                          selected_status=status,
                          search_query=search)


@admin_bp.route('/customers/<int:customer_id>')
@admin_required
def customer_detail(customer_id):
    """一般ユーザ詳細"""
    customer = Customer.query.get_or_404(customer_id)
    
    # ポイント履歴（最新20件）
    point_transactions = customer.point_transactions.order_by(
        db.text('created_at DESC')
    ).limit(20).all()
    
    # ギフト履歴（最新20件）
    gift_transactions = customer.gift_transactions.order_by(
        db.text('created_at DESC')
    ).limit(20).all()
    
    return render_template('admin/customer_detail.html',
                          customer=customer,
                          point_transactions=point_transactions,
                          gift_transactions=gift_transactions)


@admin_bp.route('/customers/<int:customer_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_customer(customer_id):
    """一般ユーザ編集"""
    customer = Customer.query.get_or_404(customer_id)
    
    if request.method == 'POST':
        nickname = request.form.get('nickname', '').strip()
        phone = request.form.get('phone', '').strip()
        
        if not nickname:
            flash('ニックネームは必須です。', 'danger')
            return render_template('admin/customer_form.html', customer=customer)
        
        old_values = {
            'nickname': customer.nickname,
            'phone': customer.phone
        }
        
        customer.nickname = nickname
        customer.phone = phone
        
        db.session.commit()
        
        audit_log('customer.edit', 'customer', customer.id,
                 old_value=old_values,
                 new_value={'nickname': nickname, 'phone': phone})
        
        flash(f'{customer.nickname}さんの情報を更新しました', 'success')
        return redirect(url_for('admin.customer_detail', customer_id=customer_id))
    
    return render_template('admin/customer_form.html', customer=customer)


@admin_bp.route('/customers/<int:customer_id>/toggle', methods=['POST'])
@admin_required
def toggle_customer(customer_id):
    """一般ユーザの有効/無効切り替え"""
    customer = Customer.query.get_or_404(customer_id)
    old_status = customer.is_active
    customer.is_active = not customer.is_active
    db.session.commit()
    
    audit_log('customer.toggle', 'customer', customer.id,
             old_value={'is_active': old_status},
             new_value={'is_active': customer.is_active})
    
    status = '有効' if customer.is_active else '無効'
    flash(f'{customer.nickname}さんを{status}にしました', 'success')
    return redirect(url_for('admin.customer_detail', customer_id=customer_id))


@admin_bp.route('/customers/<int:customer_id>/adjust-points', methods=['GET', 'POST'])
@admin_required
def adjust_customer_points(customer_id):
    """一般ユーザのポイント調整"""
    # GETリクエストの場合は詳細ページにリダイレクト
    if request.method == 'GET':
        return redirect(url_for('admin.customer_detail', customer_id=customer_id))
    
    customer = Customer.query.get_or_404(customer_id)
    
    amount = request.form.get('amount', 0, type=int)
    reason = request.form.get('reason', '').strip()
    
    if amount == 0:
        flash('調整ポイント数を入力してください', 'danger')
        return redirect(url_for('admin.customer_detail', customer_id=customer_id))
    
    old_balance = customer.point_balance
    customer.point_balance += amount
    
    # 負にならないようにする
    if customer.point_balance < 0:
        customer.point_balance = 0
    
    db.session.commit()
    
    audit_log('customer.points_adjust', 'customer', customer.id,
             old_value={'balance': old_balance},
             new_value={'balance': customer.point_balance, 'adjustment': amount, 'reason': reason})
    
    flash(f'ポイントを調整しました（{old_balance} → {customer.point_balance}）', 'success')
    return redirect(url_for('admin.customer_detail', customer_id=customer_id))


# ============================================
# User Management Extended (ユーザー管理拡張)
# ============================================

@admin_bp.route('/users/<int:user_id>')
@admin_required
def user_detail(user_id):
    """ユーザー詳細"""
    user = User.query.get_or_404(user_id)
    
    # 所属店舗
    memberships = user.shop_memberships.all()
    
    return render_template('admin/user_detail.html',
                          user=user,
                          memberships=memberships)


@admin_bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_user(user_id):
    """ユーザー編集"""
    user = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        role = request.form.get('role', 'staff')
        
        if not name:
            flash('名前は必須です。', 'danger')
            return render_template('admin/user_edit_form.html', user=user)
        
        old_values = {
            'name': user.name,
            'role': user.role
        }
        
        user.name = name
        user.role = role
        
        db.session.commit()
        
        audit_log('user.edit', 'user', user.id,
                 old_value=old_values,
                 new_value={'name': name, 'role': role})
        
        flash(f'{user.name}さんの情報を更新しました', 'success')
        return redirect(url_for('admin.user_detail', user_id=user_id))
    
    return render_template('admin/user_edit_form.html', user=user)


@admin_bp.route('/users/<int:user_id>/toggle', methods=['POST'])
@admin_required
def toggle_user(user_id):
    """ユーザーの有効/無効切り替え"""
    user = User.query.get_or_404(user_id)
    
    # 自分自身は無効化できない
    if user.id == current_user.id:
        flash('自分自身を無効化することはできません', 'danger')
        return redirect(url_for('admin.user_detail', user_id=user_id))
    
    old_status = user.is_active
    user.is_active = not user.is_active
    db.session.commit()
    
    audit_log('user.toggle', 'user', user.id,
             old_value={'is_active': old_status},
             new_value={'is_active': user.is_active})
    
    status = '有効' if user.is_active else '無効'
    flash(f'{user.name}さんを{status}にしました', 'success')
    return redirect(url_for('admin.user_detail', user_id=user_id))


@admin_bp.route('/users/<int:user_id>/reset-password', methods=['POST'])
@admin_required
def reset_user_password(user_id):
    """ユーザーのパスワードリセット"""
    user = User.query.get_or_404(user_id)
    
    # 新しいパスワードを生成
    new_password = secrets.token_urlsafe(6)
    user.set_password(new_password)
    db.session.commit()
    
    audit_log('user.password_reset', 'user', user.id)
    
    flash(f'{user.name}さんのパスワードをリセットしました', 'success')
    flash(f'🔑 新しいパスワード: {new_password}', 'info')
    return redirect(url_for('admin.user_detail', user_id=user_id))
