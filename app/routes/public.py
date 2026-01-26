"""
Night-Walk MVP - Public Routes (公開ページ)
"""
from flask import Blueprint, render_template, request, current_app
from ..models.shop import Shop, VacancyStatus
from ..models.content import Announcement, Advertisement
from ..models.gift import Cast

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
    
    # Get active casts
    casts = Cast.get_active_by_shop(shop_id)
    
    return render_template('public/shop_detail.html',
                          shop=shop,
                          job=job,
                          images=images,
                          casts=casts,
                          vacancy_labels=VacancyStatus.STATUS_LABELS,
                          vacancy_colors=VacancyStatus.STATUS_COLORS)


@public_bp.route('/casts/<int:cast_id>')
def cast_detail(cast_id):
    """キャスト詳細ページ（PVカウント発火）"""
    from flask import session
    from flask_login import current_user
    from ..extensions import db
    from ..services.ranking_service import RankingService
    
    cast = Cast.query.filter_by(id=cast_id, is_active=True).first_or_404()
    
    # 店舗が公開されているか確認
    if not cast.shop or not cast.shop.is_published or not cast.shop.is_active:
        from flask import abort
        abort(404)
    
    # PVを記録
    customer_id = None
    session_id = None
    
    if hasattr(current_user, 'is_customer') and current_user.is_customer:
        customer_id = current_user.id
    else:
        # セッションIDを使用（非ログインユーザー）
        if 'visitor_id' not in session:
            import uuid
            session['visitor_id'] = str(uuid.uuid4())
        session_id = session['visitor_id']
    
    # PV記録
    recorded = RankingService.record_page_view(
        cast_id=cast_id,
        customer_id=customer_id,
        session_id=session_id,
        ip_address=request.remote_addr,
        user_agent=request.user_agent.string if request.user_agent else None
    )
    
    if recorded:
        db.session.commit()
    
    # ギフト一覧
    from ..models.gift import Gift
    gifts = Gift.get_active_gifts()
    
    return render_template('public/cast_detail.html',
                          cast=cast,
                          shop=cast.shop,
                          gifts=gifts,
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


# ============================================
# Ranking Pages (ランキング)
# ============================================

@public_bp.route('/ranking')
def ranking_index():
    """ランキングトップ - エリア選択"""
    from ..models.ranking import AREA_DEFINITIONS
    from ..services.ranking_service import RankingService
    
    # 有効なエリア一覧
    areas = RankingService.get_active_areas()
    
    # 各エリアのTOP1を取得
    top1_list = RankingService.get_top1_casts()
    
    return render_template('public/ranking_index.html',
                          areas=areas,
                          area_definitions=AREA_DEFINITIONS,
                          top1_list=top1_list)


@public_bp.route('/ranking/<area>')
def ranking_area(area):
    """エリア別ランキング"""
    from datetime import date
    from ..models.ranking import CastMonthlyRanking, AREA_DEFINITIONS, RankingConfig
    from ..services.ranking_service import RankingService
    
    # エリア検証
    active_areas = RankingService.get_active_areas()
    if area not in active_areas:
        from flask import abort
        abort(404)
    
    # 年月パラメータ（デフォルトは前月の確定ランキング）
    today = date.today()
    if today.month == 1:
        default_year, default_month = today.year - 1, 12
    else:
        default_year, default_month = today.year, today.month - 1
    
    year = request.args.get('year', default_year, type=int)
    month = request.args.get('month', default_month, type=int)
    
    # ランキング取得
    top_count = RankingConfig.get('ranking_top_count', 100)
    rankings = CastMonthlyRanking.get_ranking(area, year, month, limit=top_count)
    
    # TOP1を特別に取得
    top1 = rankings[0] if rankings else None
    
    # エリア情報
    area_info = AREA_DEFINITIONS.get(area, {})
    
    return render_template('public/ranking_area.html',
                          area=area,
                          area_info=area_info,
                          rankings=rankings,
                          top1=top1,
                          year=year,
                          month=month)


@public_bp.route('/ranking/<area>/top1')
def ranking_top1(area):
    """エリアTOP1特集ページ（アプリの顔）"""
    from datetime import date
    from ..models.ranking import CastMonthlyRanking, CastBadgeHistory, AREA_DEFINITIONS
    from ..services.ranking_service import RankingService
    
    # エリア検証
    active_areas = RankingService.get_active_areas()
    if area not in active_areas:
        from flask import abort
        abort(404)
    
    # 年月パラメータ
    today = date.today()
    if today.month == 1:
        default_year, default_month = today.year - 1, 12
    else:
        default_year, default_month = today.year, today.month - 1
    
    year = request.args.get('year', default_year, type=int)
    month = request.args.get('month', default_month, type=int)
    
    # TOP1を取得
    top1 = CastMonthlyRanking.get_top1(area, year, month)
    
    if not top1:
        from flask import abort
        abort(404)
    
    # バッジ情報
    badge = CastBadgeHistory.query.filter_by(
        cast_id=top1.cast_id,
        area=area,
        year=year,
        month=month,
        badge_type='area_top1'
    ).first()
    
    # エリア情報
    area_info = AREA_DEFINITIONS.get(area, {})
    
    return render_template('public/ranking_top1.html',
                          area=area,
                          area_info=area_info,
                          top1=top1,
                          badge=badge,
                          year=year,
                          month=month)