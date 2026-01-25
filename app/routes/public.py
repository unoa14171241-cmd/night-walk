"""
Night-Walk MVP - Public Routes (公開ページ)
"""
from flask import Blueprint, render_template, request, current_app
from ..models.shop import Shop, VacancyStatus
from ..models.content import Announcement, Advertisement

public_bp = Blueprint('public', __name__)


@public_bp.route('/')
def index():
    """Home page - search page with announcements and ads."""
    # Get active announcements
    announcements = Announcement.get_active(limit=5)
    
    # Get banner ads
    top_ads = Advertisement.get_active(position='top', limit=3)
    
    # Get featured shops
    featured_shops = Shop.search(featured_only=True)[:6]
    
    # Get recent shops
    recent_shops = Shop.query.filter_by(
        is_published=True, 
        is_active=True
    ).order_by(Shop.created_at.desc()).limit(6).all()
    
    return render_template('public/index.html',
                          announcements=announcements,
                          top_ads=top_ads,
                          featured_shops=featured_shops,
                          recent_shops=recent_shops,
                          areas=Shop.AREAS,
                          categories=Shop.CATEGORIES,
                          category_labels=Shop.CATEGORY_LABELS,
                          price_ranges=Shop.PRICE_RANGES,
                          vacancy_labels=VacancyStatus.STATUS_LABELS,
                          vacancy_colors=VacancyStatus.STATUS_COLORS)


@public_bp.route('/search')
def search():
    """Search results page."""
    # Get search parameters
    keyword = request.args.get('q', '').strip()
    area = request.args.get('area', '')
    category = request.args.get('category', '')
    price_range_key = request.args.get('price', '')
    vacancy = request.args.get('vacancy', '')
    has_job = request.args.get('has_job', '') == '1'
    
    # Perform search
    shops = Shop.search(
        keyword=keyword if keyword else None,
        area=area if area else None,
        category=category if category else None,
        price_range_key=price_range_key if price_range_key else None,
        vacancy_status=vacancy if vacancy else None,
        has_job=has_job if has_job else None
    )
    
    # Get ads for sidebar
    sidebar_ads = Advertisement.get_active(position='sidebar', limit=2)
    
    return render_template('public/search.html',
                          shops=shops,
                          keyword=keyword,
                          selected_area=area,
                          selected_category=category,
                          selected_price=price_range_key,
                          selected_vacancy=vacancy,
                          has_job=has_job,
                          areas=Shop.AREAS,
                          categories=Shop.CATEGORIES,
                          category_labels=Shop.CATEGORY_LABELS,
                          price_ranges=Shop.PRICE_RANGES,
                          sidebar_ads=sidebar_ads,
                          vacancy_labels=VacancyStatus.STATUS_LABELS,
                          vacancy_colors=VacancyStatus.STATUS_COLORS,
                          vacancy_statuses=VacancyStatus.STATUSES[:3])  # empty, busy, full


@public_bp.route('/shops')
def shops():
    """Shop list with area filter (legacy route)."""
    area = request.args.get('area', '')
    
    query = Shop.query.filter_by(is_published=True, is_active=True)
    
    if area and area in Shop.AREAS:
        query = query.filter_by(area=area)
    
    shops = query.order_by(Shop.is_featured.desc(), Shop.name).all()
    
    return render_template('public/shop_list.html',
                          shops=shops,
                          areas=Shop.AREAS,
                          selected_area=area,
                          vacancy_labels=VacancyStatus.STATUS_LABELS,
                          vacancy_colors=VacancyStatus.STATUS_COLORS)


@public_bp.route('/shops/<int:shop_id>')
def shop_detail(shop_id):
    """Shop detail page."""
    shop = Shop.query.filter_by(
        id=shop_id,
        is_published=True,
        is_active=True
    ).first_or_404()
    
    # Get active job if any
    job = shop.active_job
    
    # Get shop images
    images = shop.all_images
    
    return render_template('public/shop_detail.html',
                          shop=shop,
                          job=job,
                          images=images,
                          vacancy_labels=VacancyStatus.STATUS_LABELS,
                          vacancy_colors=VacancyStatus.STATUS_COLORS)


@public_bp.route('/shops/<int:shop_id>/booking')
def booking(shop_id):
    """Booking page - phone reservation."""
    shop = Shop.query.filter_by(
        id=shop_id,
        is_published=True,
        is_active=True
    ).first_or_404()
    
    # Check if Twilio is configured
    twilio_configured = bool(current_app.config.get('TWILIO_ACCOUNT_SID'))
    
    return render_template('public/booking.html',
                          shop=shop,
                          twilio_configured=twilio_configured)


@public_bp.route('/ads/<int:ad_id>/click')
def ad_click(ad_id):
    """Track ad click and redirect."""
    from ..extensions import db
    
    ad = Advertisement.query.get_or_404(ad_id)
    ad.record_click()
    db.session.commit()
    
    if ad.link_url:
        from flask import redirect
        return redirect(ad.link_url)
    
    return redirect('/')
